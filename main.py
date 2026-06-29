import streamlit as st
import os
import time
import base64
import io
import math
import requests
import pandas as pd
from datetime import date, datetime, timedelta
from PIL import Image
from io import StringIO
from dotenv import load_dotenv
from cerebras.cloud.sdk import Cerebras
import json
import folium
from streamlit_folium import st_folium

# =========================
# ENV SETUP & API KEYS
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

# Load API keys from secrets/environment

CERBRAS_API_KEY = get_secret("CERBRAS_API_KEY")
FIRMS_API_KEY = get_secret("FIRMS_API_KEY")
client = Cerebras(api_key=CERBRAS_API_KEY)

# =========================
# APP CONFIG
# =========================
st.set_page_config(page_title="watchtowerV2", layout="wide")

# Inject Custom CSS for Premium Light Mode Dashboard UI
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Outfit:wght@400;600;800&family=Inter:wght@400;500;600&display=swap');
    
    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Inter', sans-serif;
        background-color: #f8fafc;
        color: #1e293b;
    }
    
    h1, h2, h3, h4, h5, h6, [data-testid="stHeader"] {
        font-family: 'Outfit', sans-serif;
        color: #0f172a;
    }
    
    .dashboard-header {
        background: linear-gradient(135deg, #ffffff, #f1f5f9);
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 25px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);
        position: relative;
        overflow: hidden;
    }
    
    .dashboard-header::before {
        content: "";
        position: absolute;
        top: 0;
        left: 0;
        width: 5px;
        height: 100%;
        background: linear-gradient(to bottom, #f97316, #ef4444);
    }
    
    .status-badge {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        background-color: rgba(239, 68, 68, 0.08);
        border: 1px solid rgba(239, 68, 68, 0.2);
        color: #dc2626;
        padding: 6px 14px;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    .status-pulse {
        width: 8px;
        height: 8px;
        background-color: #ef4444;
        border-radius: 50%;
        box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4);
        animation: pulse-red 2s infinite;
    }
    
    @keyframes pulse-red {
        0% {
            transform: scale(0.95);
            box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4);
        }
        70% {
            transform: scale(1);
            box-shadow: 0 0 0 8px rgba(239, 68, 68, 0);
        }
        100% {
            transform: scale(0.95);
            box-shadow: 0 0 0 0 rgba(239, 68, 68, 0);
        }
    }
    
    /* Sleek card designs for light mode */
    .metric-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 20px 15px;
        text-align: center;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.03);
    }
    
    .metric-value {
        font-family: 'Outfit', sans-serif;
        font-size: 1.8rem;
        font-weight: 800;
        color: #0f172a;
        margin: 5px 0;
    }
    
    .metric-label {
        font-size: 0.75rem;
        color: #64748b;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    /* Command center card styling - warm light teletype printout style */
    .dispatch-card {
        background: linear-gradient(135deg, #fffbeb, #fef3c7);
        border: 1px dashed #ef4444;
        border-radius: 12px;
        padding: 24px;
        box-shadow: 0 6px 18px rgba(239, 68, 68, 0.08);
        font-family: 'JetBrains Mono', monospace;
    }
    
    .dispatch-header {
        font-size: 1.15rem;
        color: #b91c1c;
        border-bottom: 1px solid #fcd34d;
        padding-bottom: 10px;
        margin-bottom: 18px;
        font-weight: 700;
        text-transform: uppercase;
        display: flex;
        justify-content: space-between;
    }
    
    .dispatch-row {
        margin-bottom: 14px;
        line-height: 1.5;
        font-size: 0.95rem;
    }
    
    .dispatch-label {
        color: #c2410c;
        font-weight: 700;
    }
    
    .dispatch-value {
        color: #1e293b;
    }
    
    /* Visual agent node styling for light mode */
    .agent-pipeline {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin: 20px 0 35px 0;
        padding: 20px;
        background: #f1f5f9;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        overflow-x: auto;
    }
    
    .agent-node {
        display: flex;
        flex-direction: column;
        align-items: center;
        flex: 1;
        min-width: 100px;
        position: relative;
        text-align: center;
    }
    
    .agent-node::after {
        content: "";
        position: absolute;
        top: 20px;
        left: calc(50% + 20px);
        width: calc(100% - 40px);
        height: 2px;
        background: #cbd5e1;
        z-index: 0;
    }
    
    .agent-node:last-child::after {
        display: none;
    }
    
    .agent-icon {
        width: 40px;
        height: 40px;
        background: #ffffff;
        border: 2px solid #94a3b8;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.2rem;
        z-index: 1;
        transition: all 0.3s ease;
    }
    
    .agent-node.active .agent-icon {
        background: linear-gradient(135deg, #f97316, #ef4444);
        border-color: #ef4444;
        color: #ffffff;
        box-shadow: 0 0 12px rgba(239, 68, 68, 0.4);
    }
    
    .agent-node.complete .agent-icon {
        background: #0d9488;
        border-color: #0d9488;
        color: #ffffff;
        box-shadow: 0 0 8px rgba(13, 148, 136, 0.2);
    }
    
    .agent-name {
        margin-top: 10px;
        font-size: 0.75rem;
        font-weight: 600;
        color: #64748b;
    }
    
    .agent-node.active .agent-name {
        color: #ea580c;
    }
    
    .agent-node.complete .agent-name {
        color: #0d9488;
    }
    
    /* Styled buttons */
    div.stButton > button {
        background: linear-gradient(135deg, #f97316, #ef4444) !important;
        color: white !important;
        border: none !important;
        padding: 10px 24px !important;
        font-weight: 600 !important;
        border-radius: 8px !important;
        box-shadow: 0 4px 15px rgba(239, 68, 68, 0.25) !important;
        transition: all 0.25s ease !important;
        width: 100%;
        margin-top: 10px;
    }
    
    div.stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(239, 68, 68, 0.4) !important;
        border: none !important;
    }
    
    /* Threat level badges for light mode */
    .risk-critical {
        background-color: rgba(239, 68, 68, 0.1);
        color: #b91c1c;
        border: 1px solid #fca5a5;
        padding: 6px 16px;
        border-radius: 20px;
        font-weight: 700;
        letter-spacing: 0.05em;
    }
    .risk-high {
        background-color: rgba(249, 115, 22, 0.1);
        color: #c2410c;
        border: 1px solid #fdba74;
        padding: 6px 16px;
        border-radius: 20px;
        font-weight: 700;
        letter-spacing: 0.05em;
    }
    .risk-medium {
        background-color: rgba(234, 179, 8, 0.1);
        color: #854d0e;
        border: 1px solid #fde047;
        padding: 6px 16px;
        border-radius: 20px;
        font-weight: 700;
        letter-spacing: 0.05em;
    }
    .risk-low {
        background-color: rgba(34, 197, 94, 0.1);
        color: #166534;
        border: 1px solid #86efac;
        padding: 6px 16px;
        border-radius: 20px;
        font-weight: 700;
        letter-spacing: 0.05em;
    }
    
    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #e2e8f0;
    }
    
    /* Streamlit tabs styling for light mode */
    button[data-baseweb="tab"] {
        font-family: 'Outfit', sans-serif;
        font-weight: 600;
        color: #64748b;
    }
    button[aria-selected="true"] {
        color: #ef4444 !important;
    }
    div[data-baseweb="tab-highlight-bar"] {
        background-color: #ef4444 !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# =========================
# PRE-CACHED SANDBOX DATA
# =========================
DEMO_SCENARIO = {
    "name": "Camp Fire (Paradise, California)",
    "location": "Paradise, California",
    "center_lat": 39.7596,
    "center_lon": -121.6219,
    "radius_km": 30,
    "weather": {
        "temperature_2m": 33.0,
        "wind_speed_10m": 24.0,
        "wind_direction_10m": 45,
        "relative_humidity_2m": 12
    },
    "firms": [
        {"latitude": 39.7821, "longitude": -121.5843, "frp": 85.4, "acq_date": "2026-06-28", "acq_time": 1435, "confidence": 92, "timestamp_utc": "2026-06-28 14:35 UTC"},
        {"latitude": 39.7912, "longitude": -121.5712, "frp": 110.2, "acq_date": "2026-06-28", "acq_time": 1437, "confidence": 95, "timestamp_utc": "2026-06-28 14:37 UTC"},
        {"latitude": 39.7654, "longitude": -121.6021, "frp": 45.1, "acq_date": "2026-06-28", "acq_time": 1440, "confidence": 88, "timestamp_utc": "2026-06-28 14:40 UTC"},
        {"latitude": 39.7432, "longitude": -121.6501, "frp": 12.5, "acq_date": "2026-06-28", "acq_time": 1442, "confidence": 75, "timestamp_utc": "2026-06-28 14:42 UTC"},
        {"latitude": 39.7321, "longitude": -121.6702, "frp": 8.4, "acq_date": "2026-06-28", "acq_time": 1445, "confidence": 60, "timestamp_utc": "2026-06-28 14:45 UTC"},
        {"latitude": 39.7987, "longitude": -121.5543, "frp": 140.7, "acq_date": "2026-06-28", "acq_time": 1450, "confidence": 99, "timestamp_utc": "2026-06-28 14:50 UTC"},
    ],
    "assets": [
        {"name": "CAL FIRE Station 35", "type": "fire_station", "lat": 39.7610, "lon": -121.6230},
        {"name": "Paradise Fire Station 81", "type": "fire_station", "lat": 39.7521, "lon": -121.6288},
        {"name": "Feather River Hospital", "type": "hospital", "lat": 39.7712, "lon": -121.6154},
        {"name": "Feather River Hospital Helipad", "type": "helipad", "lat": 39.7715, "lon": -121.6148},
        {"name": "Lassen National Forest Station", "type": "fire_station", "lat": 39.8050, "lon": -121.5200},
    ],
    "detection": """### 🛰️ DETECTION FUSION REPORT
**EVENT**: Multi-sensor signature confirms an active wildfire event in the vicinity of Paradise, California.
**CONFIDENCE**: 98% (High)
**LOCATION**: Butte County, CA (approx. coordinates 39.7596, -121.6219)
**SEVERITY**: CRITICAL

**ANALYSIS**: 
Satellite thermal anomalies show a cluster of 6 high-intensity detections. 
The average Fire Radiative Power (FRP) is 67.0 MW, with a peak FRP of 140.7 MW, indicating high-energy combustion and rapid fire spread. 
Plume structure from imagery is consistent with a wind-driven, high-velocity surface and canopy fire in timber/shrub fuels.""",
    "orchestrator": """### 🧭 EVENT ORCHESTRATION BRIEF
**EVENT SUMMARY**: Wind-driven wildfire spreading rapidly near Paradise, California (Butte County).
**REQUIRED ANALYSES**:
1. Weather trends (wind speed/direction, humidity drops).
2. Rate of spread modeling based on topography and fuel loads.
3. Jurisdiction and agency coordination (CAL FIRE, Butte County Sheriff, USFS).
4. Immediate asset staging and evacuation zone modeling.
**KEY UNKNOWNS**:
- Current fuel moisture levels in deep timber.
- Secondary ignition points from spotting.
- Exact status of primary evacuation routes (Skyway, Clark Road).""",
    "weather_report": """WEATHER REPORT

Temperature: 33.0 °C
Wind Speed: 24.0 km/h
Wind Direction: 45°
Humidity: 12%""",
    "context": """### 🌦️ ENVIRONMENTAL CONTEXT ASSESSMENT
**WEATHER ASSESSMENT**: 
- Temp: 33°C (Extreme dry heat)
- Wind: 24 km/h from the Northeast (NE) with gusts up to 40 km/h.
- Humidity: 12% (Critical dry fuel state).

**TERRAIN/SPREAD**: 
Steep canyons and complex topography of the Sierra Nevada foothills will create chimney effects, accelerating updrafts.
Expected spread is Southwest-ward, pushing directly toward populated residential zones of Paradise.

**ESCALATION LIKELIHOOD**: EXTREMELY HIGH. Fuels are highly receptive to spotting up to 1.5 miles ahead of the front.""",
    "risk": """CRITICAL

High risk to life, property, and critical infrastructure. Immediate evacuation required.""",
    "jurisdiction": """### ⚖️ OPERATIONAL JURISDICTION DIRECTIVE
**COUNTRY**: United States
**STATE**: California
**RESPONSIBLE AGENCIES**:
- CAL FIRE (Butte County Unit - BTU)
- Butte County Sheriff's Office (Evacuations)
- Paradise Police & Fire Departments
- US Forest Service (Lassen National Forest mutual aid)

**INCIDENT COMMAND**: Unified Command (CAL FIRE / Butte County Sheriff / Town of Paradise).""",
    "plan": """### 🧠 RESPONSE PLAN
**IMMEDIATE ACTIONS**:
1. Initiate mandatory evacuation orders for Paradise Zones 1-14.
2. Establish incident command post at Butte County Fairgrounds.
3. Deploy structure protection units to northern boundary.

**RESOURCE DEPLOYMENT**:
- Strike teams: 5 Type-1 Engine Strike Teams, 3 Dozer Strike Teams.
- Air support: 2 Type-1 VLATs (Very Large Helitankers), 3 Type-2 Helicopters.

**EVACUATION PLAN**:
- Establish contraflow on Skyway.
- Open emergency shelters at Oroville Municipal Auditorium and Silver Dollar Fairgrounds.""",
    "command": """PRIORITY: CRITICAL - LIFE SAFETY
OBJECTIVE: Contain western flank, secure evacuation corridor, protect critical water infrastructure.
ASSETS: CAL FIRE Strike Teams 9140C, VLAT Tanker 910, Air Attack 210, Butte County Evacuation Units.
IMMEDIATE ACTIONS: 
1. Sound Town of Paradise Sirens.
2. Direct all units to standby on CAL FIRE Tac 2.
3. Coordinate with PG&E for emergency power shutdowns in affected grids."""
}

# =========================
# HELPER FUNCTIONS
# =========================

@st.cache_data(ttl=3600)
def geocode_location(query):
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": query, "format": "json", "limit": 1}
    headers = {"User-Agent": "watchtower-wildfire-app"}
    try:
        r = requests.get(url, params=params, headers=headers, timeout=10)
        results = r.json()
        if not results:
            return None
        return float(results[0]["lat"]), float(results[0]["lon"]), results[0]["display_name"]
    except Exception:
        return None

@st.cache_data(ttl=1800)
def get_weather(lat, lon):
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}"
        f"&longitude={lon}"
        "&current=temperature_2m,"
        "wind_speed_10m,"
        "wind_direction_10m,"
        "relative_humidity_2m"
    )
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        data = r.json()
        current = data["current"]
        return f"""
WEATHER REPORT

Temperature: {current['temperature_2m']} °C
Wind Speed: {current['wind_speed_10m']} km/h
Wind Direction: {current['wind_direction_10m']}°
Humidity: {current['relative_humidity_2m']}%
"""
    except Exception as e:
        return f"Weather unavailable: {e}"

@st.cache_data(ttl=3600)
def get_nearby_assets(lat, lon):
    query = f"""
    [out:json];
    (
      node(around:30000,{lat},{lon})["amenity"="fire_station"];
      node(around:30000,{lat},{lon})["amenity"="hospital"];
      node(around:30000,{lat},{lon})["aeroway"="helipad"];
      node(around:30000,{lat},{lon})["aeroway"="aerodrome"];
      node(around:30000,{lat},{lon})["amenity"="shelter"];
    );
    out;
    """
    try:
        r = requests.post(
            "https://overpass-api.de/api/interpreter",
            data=query,
            timeout=60
        )
        r.raise_for_status()
        data = r.json()
        assets = []
        for e in data.get("elements", []):
            tags = e.get("tags", {})
            assets.append({
                "name": tags.get("name", "Unknown"),
                "type": tags.get("amenity") or tags.get("aeroway") or "asset",
                "lat": e.get("lat"),
                "lon": e.get("lon")
            })
        return assets
    except Exception:
        return []

@st.cache_data(ttl=300)
def fetch_firms(api_key, source, area, start_date, days=1):
    url = f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{api_key}/{source}/{area}/{days}/{start_date}"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return pd.read_csv(StringIO(r.text))

def resolve_source(selected_satellite, query_date):
    """
    NRT sources only hold a recent rolling window (roughly the last ~2 months).
    For older dates, swap to the SP (Standard Processing) equivalent, which has
    full historical coverage but a ~5 month lag before it's available.
    """
    cutoff = date.today() - timedelta(days=60)
    if query_date >= cutoff:
        return selected_satellite, False
    return selected_satellite.replace("_NRT", "_SP"), True

def parse_weather_report(weather_str):
    temp = "N/A"
    wind_speed = "N/A"
    wind_dir = "N/A"
    humidity = "N/A"
    
    if not weather_str:
        return temp, wind_speed, wind_dir, humidity
        
    for line in weather_str.split("\n"):
        if "Temperature:" in line:
            temp = line.split(":", 1)[1].replace("°C", "").strip()
        elif "Wind Speed:" in line:
            wind_speed = line.split(":", 1)[1].replace("km/h", "").strip()
        elif "Wind Direction:" in line:
            wind_dir = line.split(":", 1)[1].replace("°", "").strip()
        elif "Humidity:" in line:
            humidity = line.split(":", 1)[1].replace("%", "").strip()
            
    return temp, wind_speed, wind_dir, humidity

def create_tactical_map(center_lat, center_lon, firms_df, assets):
    # Use light tiles CartoDB Voyager
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=11,
        tiles="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png",
        attr='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
    )
    
    # Add target center marker
    folium.Marker(
        location=[center_lat, center_lon],
        popup="Target Center Coordinates",
        icon=folium.Icon(color="red", icon="crosshairs", prefix="fa")
    ).add_to(m)
    
    # Add FIRMS detections
    if firms_df is not None and not firms_df.empty:
        for _, row in firms_df.iterrows():
            lat = row.get('latitude')
            lon = row.get('longitude')
            frp = row.get('frp', 1.0)
            conf = row.get('confidence', 'N/A')
            t_utc = row.get('timestamp_utc', 'N/A')
            
            if pd.isna(lat) or pd.isna(lon):
                continue
                
            # Determine color & size based on FRP (Fire Radiative Power)
            if frp > 100:
                color = "#dc2626"
                radius = 12
            elif frp > 50:
                color = "#ea580c"
                radius = 9
            elif frp > 15:
                color = "#f97316"
                radius = 7
            else:
                color = "#f59e0b"
                radius = 5
                
            folium.CircleMarker(
                location=[lat, lon],
                radius=radius,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.7,
                weight=1.5,
                popup=folium.Popup(f"""
                <div style="font-family: 'JetBrains Mono', monospace; font-size: 11px; color: #1e293b;">
                    <strong>🔥 Thermal Anomaly</strong><br>
                    FRP: {frp:.1f} MW<br>
                    Conf: {conf}%<br>
                    Time: {t_utc}
                </div>
                """, max_width=200)
            ).add_to(m)
            
    # Add emergency assets
    if assets:
        for a in assets:
            a_lat = a.get("lat")
            a_lon = a.get("lon")
            if a_lat is not None and a_lon is not None and not pd.isna(a_lat) and not pd.isna(a_lon):
                a_type = a.get("type", "asset")
                a_name = a.get("name", "Unknown")
                
                # Determine icon & color based on asset type
                if "fire" in a_type:
                    icon_name = "fire-extinguisher"
                    icon_color = "orange"
                elif "hospital" in a_type or "medical" in a_type:
                    icon_name = "hospital"
                    icon_color = "blue"
                elif "helipad" in a_type or "aerodrome" in a_type or "airport" in a_type:
                    icon_name = "helicopter"
                    icon_color = "green"
                elif "shelter" in a_type:
                    icon_name = "home"
                    icon_color = "purple"
                else:
                    icon_name = "info"
                    icon_color = "gray"
                    
                folium.Marker(
                    location=[a_lat, a_lon],
                    popup=folium.Popup(f"""
                    <div style="font-family: 'Inter', sans-serif; font-size: 11px; color: #1e293b;">
                        <strong>🛡️ Emergency Asset</strong><br>
                        Name: {a_name}<br>
                        Type: {a_type.replace('_', ' ').capitalize()}
                    </div>
                    """, max_width=200),
                    icon=folium.Icon(color=icon_color, icon=icon_name, prefix="fa")
                ).add_to(m)
                
    return m

def render_pipeline_flow(current_step):
    steps = [
        ("Sensor Fusion", "🛰️", 1),
        ("Orchestration", "🧭", 2),
        ("Weather/Env", "🌦️", 3),
        ("Risk Evaluator", "⚠️", 4),
        ("Jurisdiction", "⚖️", 5),
        ("Response Plan", "🧠", 6),
        ("Command Dispatch", "🎯", 7)
    ]
    
    html = '<div class="agent-pipeline">'
    for name, icon, idx in steps:
        status_class = ""
        if idx < current_step:
            status_class = "complete"
        elif idx == current_step:
            status_class = "active"
            
        html += f"""
        <div class="agent-node {status_class}">
            <div class="agent-icon">{icon}</div>
            <div class="agent-name">{name}</div>
        </div>
        """
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)

# =========================
# CONTROL SIDEBAR
# =========================
st.sidebar.markdown("### ⚙️ Control Center")
system_mode = st.sidebar.radio(
    "System Mode",
    ["🧪 Sandbox Demo", "🛰️ Live Intelligence"]
)

# Initialize variables
min_lat = min_lon = max_lat = max_lon = None
center_lat = center_lon = None
display_name = ""
radius_km = 30
satellite = "VIIRS_SNPP_NRT"
uploaded_image = None
base64_image = None

if system_mode == "🧪 Sandbox Demo":
    st.sidebar.info(
        "Sandbox Demo runs with pre-cached NASA FIRMS sensor data, weather data, and multi-agent responses "
        "for the Paradise, CA Camp Fire scenario. No API credentials are required."
    )
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("**Target Profile (Pre-cached):**")
    st.sidebar.markdown("📍 Location: **Paradise, California**")
    st.sidebar.markdown("📡 Source: **VIIRS_SNPP_NRT**")
    st.sidebar.markdown("📏 Radius: **30 km**")
    
    # Set demo coordinates
    center_lat = DEMO_SCENARIO["center_lat"]
    center_lon = DEMO_SCENARIO["center_lon"]
    display_name = DEMO_SCENARIO["location"]
    radius_km = DEMO_SCENARIO["radius_km"]
    
    lat_delta = radius_km / 111.0
    lon_delta = radius_km / (111.0 * math.cos(math.radians(center_lat)))
    min_lat = center_lat - lat_delta
    max_lat = center_lat + lat_delta
    min_lon = center_lon - lon_delta
    max_lon = center_lon + lon_delta

else:
    st.sidebar.info(
        "Live Intelligence makes live calls to NASA FIRMS, geocoding, weather APIs, "
        "and runs live Cerebras LLM agents in the background."
    )
    
    st.sidebar.markdown("---")
    location_query = st.sidebar.text_input(
        "Enter a location",
        value="Paradise, California",
        placeholder="e.g. Paradise, California or Lake Tahoe"
    )
    
    radius_km = st.sidebar.slider("Search radius (km)", min_value=5, max_value=150, value=30)
    
    satellite = st.sidebar.selectbox(
        "Satellite Source",
        ["VIIRS_SNPP_NRT", "VIIRS_NOAA20_NRT", "MODIS_NRT"]
    )
    
    # Single date selector as per the friend's modifications
    start_date = st.sidebar.date_input("Start Date", date.today() - timedelta(days=3))
    
    if location_query:
        geo = geocode_location(location_query)
        if geo:
            center_lat, center_lon, display_name = geo
            st.sidebar.success(f"📍 {display_name[:30]}...")
            
            lat_delta = radius_km / 111.0
            lon_delta = radius_km / (111.0 * math.cos(math.radians(center_lat)))
            min_lat = center_lat - lat_delta
            max_lat = center_lat + lat_delta
            min_lon = center_lon - lon_delta
            max_lon = center_lon + lon_delta
        else:
            st.sidebar.error("Location not found.")

# Input sections in main page
st.subheader("🛰️ Bounding Box & Satellite Feed Input")
col_inp1, col_inp2 = st.columns([1, 1])

with col_inp1:
    uploaded_image = st.file_uploader("Upload local satellite imagery (optional)", type=["png", "jpg", "jpeg"])
    if uploaded_image:
        image = Image.open(uploaded_image)
        if image.mode != "RGB":
            image = image.convert("RGB")
        st.image(image, caption="Satellite Feed (Local)", use_container_width=True)
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG")
        base64_image = base64.b64encode(buffer.getvalue()).decode()

with col_inp2:
    if center_lat and center_lon:
        st.markdown(f"**Bounding Box Center:** `{center_lat:.4f}, {center_lon:.4f}`")
        st.map(pd.DataFrame({"lat": [center_lat], "lon": [center_lon]}), zoom=9)

# Live Mode: Fetch FIRMS Data Button
firms_df = None
if system_mode == "🛰️ Live Intelligence":
    if st.button("Fetch FIRMS Data"):
        if min_lat is None:
            st.warning("Enter a valid location first.")
        else:
            with st.spinner("Fetching FIRMS detections..."):
                # Use resolve_source to map old NRT sources to SP sources
                resolved_satellite, swapped = resolve_source(satellite, start_date)
                if swapped:
                    st.info(f"Date is older than ~2 months — using {resolved_satellite} instead of {satellite}.")

                area = f"{min_lon:.4f},{min_lat:.4f},{max_lon:.4f},{max_lat:.4f}"
                try:
                    firms_df = fetch_firms(
                        FIRMS_API_KEY,
                        resolved_satellite,
                        area,
                        start_date.strftime("%Y-%m-%d"),
                        days=1
                    )
                    
                    if firms_df.empty:
                        st.warning(
                            "No detections returned. If this date is within the last ~5 months, "
                            "it may fall in the gap between NRT expiry and SP availability."
                        )
                    
                    if "acq_date" in firms_df.columns and "acq_time" in firms_df.columns:
                        firms_df["acq_time"] = (
                            firms_df["acq_time"]
                            .fillna(0)
                            .astype(int)
                            .astype(str)
                            .str.zfill(4)
                        )
                        firms_df["timestamp_utc"] = firms_df.apply(
                            lambda row: f"{row['acq_date']} {row['acq_time'][:2]}:{row['acq_time'][2:]} UTC",
                            axis=1
                        )
                    
                    st.session_state["firms"] = firms_df
                    st.success(f"Loaded {len(firms_df)} FIRMS detections")
                except Exception as e:
                    st.error(f"Error fetching FIRMS data: {e}")

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

def agent(prompt, context):
    return client.chat.completions.create(
        model="gemma-4-31b",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": context}
        ],
        max_completion_tokens=250
    ).choices[0].message.content

# Simplified Agent System Prompts as per friend's code
ORCH = "You are an orchestrator. Break events into tasks."
CTX = "You analyze environmental context."
RISK = "You analyze severity and escalation speed. Return LOW, MEDIUM, HIGH, or CRITICAL."
JUR = "You determine jurisdiction and authority."
PLAN = "You generate response strategy."
CMD = "You issue final operational command."

# =========================
# RUN PIPELINE
# =========================
st.markdown("### 🧠 Watchtower Multi-Agent Pipeline Execution")
if st.button("🚀 Run System Analysis"):
    if system_mode == "🧪 Sandbox Demo":
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        steps = [
            ("Initializing Multi-Sensor Fusion Pipeline...", 0.1),
            ("Running Detection Fusion Agent...", 0.25),
            ("Running Event Orchestrator...", 0.4),
            ("Fetching Environmental Context...", 0.55),
            ("Evaluating Risk Thresholds...", 0.7),
            ("Determining Jurisdiction Authorities...", 0.85),
            ("Formulating Command Dispatch...", 1.0)
        ]
        
        for msg, progress in steps:
            status_text.text(msg)
            time.sleep(0.3)
            progress_bar.progress(progress)
            
        status_text.empty()
        progress_bar.empty()
        
        # Load pre-cached demo data into session state
        st.session_state["firms"] = pd.DataFrame(DEMO_SCENARIO["firms"])
        st.session_state["detection"] = DEMO_SCENARIO["detection"]
        st.session_state["orchestrator"] = DEMO_SCENARIO["orchestrator"]
        st.session_state["weather_report"] = DEMO_SCENARIO["weather_report"]
        st.session_state["context"] = DEMO_SCENARIO["context"]
        st.session_state["risk"] = DEMO_SCENARIO["risk"]
        st.session_state["jurisdiction"] = DEMO_SCENARIO["jurisdiction"]
        st.session_state["plan"] = DEMO_SCENARIO["plan"]
        st.session_state["command"] = DEMO_SCENARIO["command"]
        st.session_state["nearby_assets"] = DEMO_SCENARIO["assets"]
        st.session_state["elapsed"] = 1.84
        st.session_state["has_run"] = True
        
    else:
        if not base64_image and (firms_df is None or firms_df.empty):
            st.warning("Provide satellite image or fetch FIRMS data first.")
        else:
            t0 = time.time()
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Step 1: Fusion Agent
            status_text.text("Executing Detection Fusion Agent...")
            progress_bar.progress(0.15)
            detection = detection_fusion_agent(base64_image, firms_df)
            
            # Step 2: Orchestrator
            status_text.text("Orchestrating Event Tasks...")
            progress_bar.progress(0.30)
            orchestrator = agent(ORCH, detection)
            
            # Step 3: Tools Fetch
            status_text.text("Retrieving Environmental Weather Data...")
            progress_bar.progress(0.45)
            weather_report = "Unavailable"
            if center_lat and center_lon:
                weather_report = get_weather(center_lat, center_lon)
                
            status_text.text("Querying Emergency Infrastructure Assets...")
            progress_bar.progress(0.60)
            nearby_assets = []
            if center_lat and center_lon:
                nearby_assets = get_nearby_assets(center_lat, center_lon)
                
            asset_text = ""
            if nearby_assets:
                asset_text = "\n".join([f"- {a['type']}: {a['name']}" for a in nearby_assets[:20]])
            else:
                asset_text = "No nearby assets found."
                
            # Step 4: Context
            status_text.text("Analyzing Environmental Context...")
            progress_bar.progress(0.72)
            context = agent(CTX, detection)
            
            # Step 5: Risk
            status_text.text("Evaluating Risk Threat Levels...")
            progress_bar.progress(0.80)
            risk = agent(RISK, detection)
            
            # Step 6: Jurisdiction
            status_text.text("Determining Jurisdiction Authorities...")
            progress_bar.progress(0.88)
            jurisdiction = agent(JUR, detection)
            
            # Step 7: Response Planner
            status_text.text("Formulating Strategic Response Plan...")
            progress_bar.progress(0.94)
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
            
            # Step 8: Final Command
            status_text.text("Generating Operational Dispatch Orders...")
            progress_bar.progress(0.98)
            command = agent(CMD, plan)
            
            progress_bar.progress(1.0)
            elapsed = time.time() - t0
            
            status_text.empty()
            progress_bar.empty()
            
            # Cache responses in Streamlit Session State
            st.session_state["detection"] = detection
            st.session_state["orchestrator"] = orchestrator
            st.session_state["weather_report"] = weather_report
            st.session_state["context"] = context
            st.session_state["risk"] = risk
            st.session_state["jurisdiction"] = jurisdiction
            st.session_state["plan"] = plan
            st.session_state["command"] = command
            st.session_state["nearby_assets"] = nearby_assets
            st.session_state["elapsed"] = elapsed
            st.session_state["has_run"] = True

# =========================
# DISPLAY RESULTS
# =========================
if st.session_state.get("has_run"):
    elapsed = st.session_state.get("elapsed", 0.0)
    st.success(f"Pipeline analysis completed in {round(elapsed, 2)} seconds")
    
    # Create Tabbed Dashboard
    tab1, tab2, tab3, tab4 = st.tabs([
        "🌐 Tactical Map & Feeds",
        "📊 Environment & Assets",
        "🧠 Multi-Agent Pipeline",
        "🎯 Command Dispatch"
    ])
    
    with tab1:
        col_map, col_img = st.columns([2, 1])
        with col_map:
            st.subheader("🗺️ Tactical Incident Map")
            m = create_tactical_map(
                center_lat, 
                center_lon, 
                st.session_state.get("firms"), 
                st.session_state.get("nearby_assets")
            )
            st_folium(m, height=450, width=None, key="tactical_map")
            
        with col_img:
            st.subheader("📷 Satellite Imagery")
            if uploaded_image:
                st.image(image, caption="Satellite Feed (Uploaded)", use_container_width=True)
            elif system_mode == "🧪 Sandbox Demo":
                st.info("Demo mode satellite imagery analysis active. View thermal hotspots mapped on the left.")
            else:
                st.info("No satellite image uploaded. System is running based on FIRMS telemetry coordinates.")
                
    with tab2:
        st.subheader("🌦️ Environmental Conditions")
        w_report = st.session_state.get("weather_report", "")
        t, ws, wd, h = parse_weather_report(w_report)
        
        # Render weather metric cards
        col_w1, col_w2, col_w3, col_w4 = st.columns(4)
        with col_w1:
            st.markdown(f'<div class="metric-card"><div class="metric-label">🌡️ Temperature</div><div class="metric-value">{t} °C</div></div>', unsafe_allow_html=True)
        with col_w2:
            st.markdown(f'<div class="metric-card"><div class="metric-label">💨 Wind Speed</div><div class="metric-value">{ws} km/h</div></div>', unsafe_allow_html=True)
        with col_w3:
            st.markdown(f'<div class="metric-card"><div class="metric-label">🧭 Wind Direction</div><div class="metric-value">{wd}°</div></div>', unsafe_allow_html=True)
        with col_w4:
            st.markdown(f'<div class="metric-card"><div class="metric-label">💧 Humidity</div><div class="metric-value">{h}%</div></div>', unsafe_allow_html=True)
            
        st.markdown("---")
        
        st.subheader("🔥 NASA FIRMS Telemetry")
        f_df = st.session_state.get("firms")
        if f_df is not None and not f_df.empty:
            detections = len(f_df)
            avg_frp = f"{f_df['frp'].mean():.1f} MW"
            max_frp = f"{f_df['frp'].max():.1f} MW"
            high_intensity = len(f_df[f_df['frp'] > 10])
            
            col_f1, col_f2, col_f3, col_f4 = st.columns(4)
            with col_f1:
                st.markdown(f'<div class="metric-card"><div class="metric-label">🔥 Detections</div><div class="metric-value">{detections}</div></div>', unsafe_allow_html=True)
            with col_f2:
                st.markdown(f'<div class="metric-card"><div class="metric-label">⚡ Avg FRP</div><div class="metric-value">{avg_frp}</div></div>', unsafe_allow_html=True)
            with col_f3:
                st.markdown(f'<div class="metric-card"><div class="metric-label">💥 Max FRP</div><div class="metric-value">{max_frp}</div></div>', unsafe_allow_html=True)
            with col_f4:
                st.markdown(f'<div class="metric-card"><div class="metric-label">⚠️ High Intensity</div><div class="metric-value">{high_intensity}</div></div>', unsafe_allow_html=True)
        else:
            st.info("No active thermal detections inside bounding box.")
            
        st.markdown("---")
        
        st.subheader("🚒 Emergency Infrastructure Assets (30km Radius)")
        assets_list = st.session_state.get("nearby_assets", [])
        if assets_list:
            st.dataframe(pd.DataFrame(assets_list), use_container_width=True)
        else:
            st.info("No nearby assets found via OSM Overpass API.")
            
    with tab3:
        st.subheader("🧠 Multi-Agent Analytical Output")
        
        # Render visual pipeline progress
        render_pipeline_flow(8)
        
        # Threat level badge
        risk_clean = st.session_state.get("risk", "").strip().upper()
        risk_class = "risk-low"
        risk_label = "LOW"
        if "CRITICAL" in risk_clean:
            risk_class = "risk-critical"
            risk_label = "CRITICAL"
        elif "HIGH" in risk_clean:
            risk_class = "risk-high"
            risk_label = "HIGH"
        elif "MEDIUM" in risk_clean:
            risk_class = "risk-medium"
            risk_label = "MEDIUM"
            
        st.markdown(f"""
        <div style="background: #ffffff; padding: 18px; border-radius: 8px; border: 1px solid #e2e8f0; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 4px 10px rgba(0,0,0,0.03);">
            <div>
                <h4 style="margin: 0; font-size: 1.1rem; color: #0f172a;">Threat Assessment Level</h4>
                <p style="margin: 5px 0 0 0; font-size: 0.85rem; color: #64748b;">Determined by Risk Assessment Agent based on sensor data & context</p>
            </div>
            <div class="{risk_class}">
                {risk_label}
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Expanders for detailed reports
        with st.expander("🛰️ Detection Fusion Agent Report", expanded=True):
            st.markdown(st.session_state.get("detection"))
            
        with st.expander("🧭 Event Orchestrator Brief", expanded=False):
            st.markdown(st.session_state.get("orchestrator"))
            
        with st.expander("🌦️ Environmental Context Assessment", expanded=False):
            st.markdown(st.session_state.get("context"))
            
        with st.expander("⚖️ Operational Jurisdiction Directive", expanded=False):
            st.markdown(st.session_state.get("jurisdiction"))
            
    with tab4:
        st.subheader("🎯 Strategic Response Command")
        
        # Final Command Card
        cmd_output = st.session_state.get("command", "")
        lines = cmd_output.split("\n")
        html_lines = []
        for line in lines:
            if ":" in line:
                parts = line.split(":", 1)
                html_lines.append(f'<div class="dispatch-row"><span class="dispatch-label">{parts[0].strip()}:</span> <span class="dispatch-value">{parts[1].strip()}</span></div>')
            else:
                html_lines.append(f'<div class="dispatch-row"><span class="dispatch-value">{line}</span></div>')
                
        st.markdown(f"""
        <div class="dispatch-card">
            <div class="dispatch-header">
                <span>🚨 OPERATIONAL DISPATCH ORDER</span>
                <span style="color: #b91c1c; font-size: 0.8rem; font-weight: normal; font-family: sans-serif;">STRICT CONFIDENTIALITY</span>
            </div>
            {"".join(html_lines)}
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        st.subheader("📋 Response & Deployment Plan Details")
        st.markdown(st.session_state.get("plan"))

else:
    st.markdown(
        """
        <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 40px 20px; text-align: center; margin-top: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.05);">
            <span style="font-size: 3rem;">🛰️</span>
            <h3 style="margin-top: 15px; color: #0f172a; font-family: 'Outfit', sans-serif;">Multi-Sensor Fusion Pipeline Idle</h3>
            <p style="color: #64748b; max-width: 500px; margin: 10px auto; font-size: 0.95rem;">
                Select a mode in the sidebar, configure target parameters, and click <strong>🚀 Run System Analysis</strong> to orchestrate the multi-agent detection and response plan.
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

# =========================
# FOOTER
# =========================
st.markdown("---")
st.caption("watchtowerV2 — Multi-Sensor Fusion + Multi-Agent Decision System")
