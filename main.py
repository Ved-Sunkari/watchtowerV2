import streamlit as st
import os
import time
import base64
import io
import math
import requests
import pandas as pd
from PIL import Image
from io import StringIO
from dotenv import load_dotenv
from cerebras.cloud.sdk import Cerebras

# =========================
# ENV SETUP
# =========================
load_dotenv()


def get_secret(name):
    try:
        value = st.secrets.get(name)
    except (FileNotFoundError, KeyError):
        value = None

    if not value:
        value = os.getenv(name)

    if not value:
        st.error(
            f"Missing required secret: {name}. Add it in Streamlit secrets "
            "or set it in a local .env file."
        )
        st.stop()

    return value


CERBRAS_API_KEY = get_secret("CERBRAS_API_KEY")
FIRMS_API_KEY = get_secret("FIRMS_API_KEY")
client = Cerebras(api_key=CERBRAS_API_KEY)

# =========================
# APP CONFIG
# =========================
st.set_page_config(page_title="watchtowerV2", layout="wide")
st.title("🌍 watchtowerV2 — Multi-Sensor Intelligence System")

# =========================
# INPUTS
# =========================
st.subheader("🛰️ Satellite Image Input")

uploaded_image = st.file_uploader("Upload satellite image", type=["png", "jpg", "jpeg"])

base64_image = None

if uploaded_image:
    image = Image.open(uploaded_image)

    if image.mode != "RGB":
        image = image.convert("RGB")

    st.image(image, caption="Satellite Feed", use_container_width=True)

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    base64_image = base64.b64encode(buffer.getvalue()).decode()

# =========================
# LOCATION INPUT
# =========================
st.subheader("📍 Location")

location_query = st.text_input(
    "Enter a location",
    placeholder="e.g. Paradise, California or Lake Tahoe"
)
radius_km = st.slider("Search radius (km)", min_value=5, max_value=150, value=30)

satellite = st.selectbox(
    "Satellite Source",
    ["VIIRS_SNPP_NRT", "VIIRS_NOAA20_NRT", "MODIS_NRT"]
)

from datetime import datetime, timedelta

col1, col2 = st.columns(2)

with col1:
    start_date = st.date_input(
        "Start Date",
        datetime.utcnow() - timedelta(days=3)
    )

with col2:
    end_date = st.date_input(
        "End Date",
        datetime.utcnow()
    )


@st.cache_data(ttl=3600)
def geocode_location(query):
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": query, "format": "json", "limit": 1}
    headers = {"User-Agent": "watchtower-wildfire-app"}  # Nominatim requires a User-Agent
    r = requests.get(url, params=params, headers=headers, timeout=10)
    results = r.json()
    if not results:
        return None
    return float(results[0]["lat"]), float(results[0]["lon"]), results[0]["display_name"]


min_lat = min_lon = max_lat = max_lon = None
center_lat = center_lon = None

if location_query:
    geo = geocode_location(location_query)
    if geo:
        center_lat, center_lon, display_name = geo
        st.success(f"📍 {display_name}")

        # Convert a radius in km to a lat/lon bounding box.
        # Longitude degrees shrink as you move away from the equator,
        # so we correct using cos(latitude).
        lat_delta = radius_km / 111.0
        lon_delta = radius_km / (111.0 * math.cos(math.radians(center_lat)))

        min_lat = center_lat - lat_delta
        max_lat = center_lat + lat_delta
        min_lon = center_lon - lon_delta
        max_lon = center_lon + lon_delta

        st.map(pd.DataFrame({"lat": [center_lat], "lon": [center_lon]}), zoom=8)

        # Heads up if the geocoded point is way bigger than the search radius
        # (e.g. typing a whole province/state name returns one centroid point,
        # and a small radius around it can miss real fire activity entirely).
        if any(tok in display_name for tok in [
            "Province", "State", "Territory", "Region"
        ]) and "," not in display_name.split(",")[0]:
            st.info(
                "📌 Heads up: this resolved to a broad region, not a specific town. "
                "A small search radius around its centroid may miss fires that "
                "occurred elsewhere in the region. Try a specific city/town name "
                "or increase the radius."
            )
    else:
        st.error("Couldn't find that location — try being more specific.")


# =========================
# FIRMS FETCH FUNCTION
# =========================

@st.cache_data(ttl=300)
def fetch_firms(api_key, source, area, start_date, days):
    url = (
        f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/"
        f"{api_key}/{source}/{area}/{days}/{start_date}"
    )

    r = requests.get(url, timeout=30)
    r.raise_for_status()

    text = r.text.strip()
    first_line = text.splitlines()[0] if text else ""

    # FIRMS returns errors (bad key, bad source/area, etc.) as plain text
    # with a 200 OK status, so raise_for_status() above never catches them.
    # Without this check, pd.read_csv silently parses the error string as
    # a 1-column, 0-row header and you get a misleading "0 detections".
    if not text or "Invalid" in first_line or "Error" in first_line:
        raise ValueError(f"FIRMS rejected the request: {first_line!r}")

    df = pd.read_csv(StringIO(text))

    expected = {"latitude", "longitude", "acq_date", "frp"}
    if not expected.issubset(df.columns):
        raise ValueError(
            f"Unexpected FIRMS response (no fire-detection columns found). "
            f"Got columns: {list(df.columns)} | raw start: {text[:200]!r}"
        )

    return df, url


firms_df = None

if st.button("Fetch FIRMS Data"):

    if min_lat is None:
        st.warning("Enter a valid location first.")
        st.stop()

    if end_date < start_date:
        st.error("End date must be after start date.")
        st.stop()

    with st.spinner("Fetching FIRMS detections..."):

        area = f"{min_lon},{min_lat},{max_lon},{max_lat}"

        delta = end_date - start_date
        dfs = []
        debug_requests = []  # (url, status) pairs for the debug panel

        # FIRMS area API caps DAY_RANGE at 5, so we chunk in 5-day windows
        for i in range(0, delta.days + 1, 5):

            chunk_start = start_date + timedelta(days=i)
            chunk_end = min(
                start_date + timedelta(days=i + 4),
                end_date
            )

            chunk_days = (chunk_end - chunk_start).days + 1

            try:
                df_chunk, used_url = fetch_firms(
                    FIRMS_API_KEY,
                    satellite,
                    area,
                    chunk_start.strftime("%Y-%m-%d"),
                    chunk_days
                )

                dfs.append(df_chunk)
                debug_requests.append((used_url, f"OK — {len(df_chunk)} rows"))

            except Exception as e:
                st.warning(
                    f"Could not fetch data for "
                    f"{chunk_start} - {chunk_end}: {e}"
                )
                debug_requests.append((
                    f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/"
                    f"{FIRMS_API_KEY}/{satellite}/{area}/{chunk_days}/"
                    f"{chunk_start.strftime('%Y-%m-%d')}",
                    f"FAILED — {e}"
                ))

        with st.expander("🔍 Debug: requests sent to FIRMS"):
            st.write(f"Bounding box (west,south,east,north): `{area}`")
            for u, status in debug_requests:
                st.code(u)
                st.caption(status)

        if dfs:
            firms_df = pd.concat(dfs, ignore_index=True)

            if "acq_date" in firms_df.columns and "acq_time" in firms_df.columns:

                firms_df = firms_df.convert_dtypes(
                    dtype_backend="numpy_nullable"
                )

                dates = firms_df["acq_date"].astype(str).tolist()

                times = (
                    firms_df["acq_time"]
                    .fillna(0)
                    .astype(int)
                    .astype(str)
                    .str.zfill(4)
                    .tolist()
                )

                firms_df["timestamp_utc"] = [
                    f"{d} {t[:2]}:{t[2:]} UTC"
                    for d, t in zip(dates, times)
                ]
            st.session_state["firms"] = firms_df

            if len(firms_df) == 0:
                st.warning(
                    "FIRMS returned valid (empty) results — no detections in "
                    "this area/date/source combo. Check the debug panel above: "
                    "copy one of the URLs into your browser to confirm, and try "
                    "widening the radius or double-checking the location."
                )
            else:
                st.success(
                    f"Loaded {len(firms_df)} FIRMS detections"
                )

        else:
            st.error("No FIRMS detections found.")

firms_df = st.session_state.get("firms")


# =========================
# FUSION DETECTION AGENT
# =========================
def detection_fusion_agent(image_b64, firms_df):

    firms_summary = "No FIRMS data available."

    if firms_df is not None and not firms_df.empty:
        firms_summary = f"""
FIRMS SENSOR DATA:
- Detections: {len(firms_df)}
- Avg FRP: {firms_df['frp'].mean():.2f}
- Max FRP: {firms_df['frp'].max():.2f}
- High intensity (>10 FRP): {len(firms_df[firms_df['frp'] > 10])}
"""

    if image_b64:
        content = [
            {"type": "text", "text": f"""
You are the Detection Fusion Agent.

Combine satellite image + FIRMS data into ONE structured event.

Return:
- What is happening
- Confidence
- Location interpretation
- Severity

{firms_summary}
"""},
            {"type": "image_url", "image_url": {
                "url": f"data:image/jpeg;base64,{image_b64}"
            }}
        ]
    else:
        content = [{"type": "text", "text": f"""
No image available.

Use FIRMS only.

{firms_summary}
"""}]

    return client.chat.completions.create(
        model="gemma-4-31b",
        messages=[{"role": "user", "content": content}],
        max_completion_tokens=350
    ).choices[0].message.content


# =========================
# OTHER AGENTS
# =========================
def agent(prompt, context):
    return client.chat.completions.create(
        model="gemma-4-31b",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": context}
        ],
        max_completion_tokens=250
    ).choices[0].message.content


ORCH = "You are an orchestrator. Break events into tasks."
CTX = "You analyze environmental context."
RISK = "You analyze severity and escalation speed."
JUR = "You determine jurisdiction and authority."
PLAN = "You generate response strategy."
CMD = "You issue final operational command."


# =========================
# RUN PIPELINE
# =========================
st.subheader("🧠 Watchtower Multi-Agent Pipeline")

if st.button("🚀 Run System"):

    if not base64_image and (firms_df is None or firms_df.empty):
        st.warning("Provide image or FIRMS data.")
        st.stop()

    t0 = time.time()

    # 1. DETECTION FUSION LAYER
    detection = detection_fusion_agent(base64_image, firms_df)

    # 2. ORCHESTRATOR
    orchestrator = agent(ORCH, detection)

    # 3. SPECIALISTS
    context = agent(CTX, detection)
    risk = agent(RISK, detection)
    jurisdiction = agent(JUR, detection)

    # 4. PLANNER
    planner_input = f"""
DETECTION:
{detection}

ORCHESTRATOR:
{orchestrator}

CONTEXT:
{context}

RISK:
{risk}

JURISDICTION:
{jurisdiction}
"""

    plan = agent(PLAN, planner_input)

    # 5. COMMAND
    command = agent(CMD, plan)

    elapsed = time.time() - t0

    # =========================
    # OUTPUT
    # =========================
    st.success(f"Completed in {round(elapsed,2)}s")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("## 🛰️ Detection Fusion Layer")
        st.write(detection)

        st.markdown("## 🧭 Orchestrator")
        st.write(orchestrator)

        st.markdown("## 🌍 Context")
        st.write(context)

        st.markdown("## ⚖️ Jurisdiction")
        st.write(jurisdiction)

    with col2:
        st.markdown("## ⚠️ Risk")
        st.write(risk)

        st.markdown("## 🧠 Response Plan")
        st.write(plan)

        st.markdown("## 🎯 Command Output")
        st.write(command)

# =========================
# FOOTER
# =========================
st.markdown("---")
st.caption("watchtowerV2 — Multi-Sensor Fusion + Multi-Agent Decision System")
