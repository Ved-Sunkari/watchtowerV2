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

start_date = st.date_input("Start Date")


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
    else:
        st.error("Couldn't find that location — try being more specific.")


# =========================
# FIRMS FETCH FUNCTION
# =========================
@st.cache_data(ttl=300)
def fetch_firms(api_key, source, area, start_date, days=1):
    url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{api_key}/{source}/{area}/{days}/{start_date}"
    r = requests.get(url)
    return pd.read_csv(StringIO(r.text))


firms_df = None

if st.button("Fetch FIRMS Data"):
    if min_lat is None:
        st.warning("Enter a valid location first.")
        st.stop()

    area = f"{min_lon},{min_lat},{max_lon},{max_lat}"
    firms_df = fetch_firms(FIRMS_API_KEY, satellite, area, start_date.strftime("%Y-%m-%d"))
    st.session_state["firms"] = firms_df
    st.success(f"Loaded {len(firms_df)} FIRMS detections")

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
