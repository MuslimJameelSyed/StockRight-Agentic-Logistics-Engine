"""
Warehouse Putaway Recommendation - Streamlit App
"""

import streamlit as st
import mysql.connector
from qdrant_client import QdrantClient
import google.generativeai as genai
import logging
import pandas as pd

# Import configuration and error handling
from config import config, ConfigurationError
from error_handler import (
    retry_on_failure,
    audit_logger,
    DatabaseConnectionError,
    QdrantConnectionError,
    PartNotFoundError
)

logger = logging.getLogger(__name__)

@st.cache_resource
def get_qdrant():
    try:
        logger.info("Initializing Qdrant connection...")
        client = QdrantClient(url=config.QDRANT_URL, api_key=config.QDRANT_API_KEY)
        logger.info("Qdrant connection established")
        return client
    except Exception as e:
        logger.error(f"Failed to connect to Qdrant: {str(e)}")
        raise QdrantConnectionError(f"Could not connect to Qdrant: {str(e)}")

@st.cache_resource
def get_db():
    try:
        logger.info("Initializing Cloud SQL connection...")
        db = mysql.connector.connect(**config.get_db_config())
        logger.info("Cloud SQL connection established")
        return db
    except Exception as e:
        logger.error(f"Failed to connect to Cloud SQL: {str(e)}")
        raise DatabaseConnectionError(f"Could not connect to database: {str(e)}")

@st.cache_resource
def get_gemini_model():
    try:
        logger.info("Initializing Gemini AI...")
        genai.configure(api_key=config.GEMINI_API_KEY)
        model = genai.GenerativeModel(config.GEMINI_MODEL)
        logger.info("Gemini AI initialized")
        return model
    except Exception as e:
        logger.error(f"Failed to initialize Gemini: {str(e)}")
        st.error(f"AI service unavailable: {str(e)}")
        return None

def is_valid_location(location_code):
    if not location_code: return False
    if location_code.startswith(("FLOOR", "REC", "ORD")): return False
    if len(location_code) >= 2:
        last_two = location_code[-2:]
        if last_two.isalpha() and last_two[0] == last_two[1]:
            return False
    return True

def check_location_availability(location_code, cursor):
    cursor.execute("SELECT clientId FROM location WHERE code = %s", (location_code,))
    result = cursor.fetchone()
    if not result: return "UNKNOWN"
    return "FREE" if result[0] is None else "OCCUPIED"

@retry_on_failure(max_retries=config.MAX_RETRIES, delay=1.0)
def get_part_from_qdrant(qdrant, part_id):
    try:
        results = qdrant.retrieve(collection_name=config.QDRANT_COLLECTION_NAME, ids=[part_id])
        return results[0].payload if results else None
    except Exception as e:
        logger.error(f"Qdrant retrieval error for part {part_id}: {str(e)}")
        raise

def call_gemini(model, prompt):
    try:
        response = model.generate_content(
            prompt,
            generation_config={"temperature": 0.1, "max_output_tokens": 1024},
        )
        if response.candidates and response.candidates[0].content.parts:
            return response.candidates[0].content.parts[0].text
    except Exception:
        pass
    return None

def get_recommendation(part_id: int):
    qdrant = get_qdrant()
    db = get_db()
    model = get_gemini_model()

    if not db.is_connected():
        db.reconnect()

    cursor = db.cursor()

    cursor.execute("SELECT id, code, description, clientId FROM part WHERE id = %s", (part_id,))
    row = cursor.fetchone()
    if not row:
        cursor.close()
        return {"error": f"Part {part_id} not found in database."}

    _, part_code, description, client_id = row

    cursor.execute("SELECT name FROM client WHERE id = %s", (client_id,))
    client_row = cursor.fetchone()
    client_name = client_row[0] if client_row else f"Client {client_id}"

    part_info = {
        "part_id": part_id,
        "part_code": part_code,
        "description": description or "N/A",
        "client_name": client_name,
        "client_id": client_id,
    }

    qdrant_data = get_part_from_qdrant(qdrant, part_id)

    if not qdrant_data or not qdrant_data.get("all_locations"):
        zone = qdrant_data.get("primary_zone") if qdrant_data else None
        zone_text = f"Zone {zone}" if zone else "any available zone"
        cursor.close()
        return {
            **part_info,
            "status": "no_history",
            "ai_summary": (
                f"This part has no historical putaway data. "
                f"Consult your supervisor — consider placing it in {zone_text}."
            ),
        }

    locations = qdrant_data["all_locations"]
    available = []
    for loc in locations:
        code = loc.get("code")
        if not is_valid_location(code):
            continue
        if check_location_availability(code, cursor) == "FREE":
            available.append(
                {"code": code, "count": loc.get("count", 0), "percentage": loc.get("percentage", 0)}
            )

    available.sort(key=lambda x: -x["count"])
    total_putaways = qdrant_data.get("total_putaways", 0)
    cursor.close()

    if not available:
        zone = qdrant_data.get("primary_zone", "Unknown")
        prompt = (
            f"You are a warehouse management assistant. "
            f"All previously used warehouse shelf locations for part '{part_code}' ({description}) "
            f"belonging to client '{client_name}' are currently occupied. The preferred warehouse zone is {zone}. "
            f"In one sentence, advise the warehouse operator what to do next."
        )
        ai_text = call_gemini(model, prompt) or (
            f"All historical locations are occupied — consult your supervisor "
            f"and look for a free location in Zone {zone}."
        )
        return {**part_info, "status": "all_occupied", "ai_summary": ai_text, "zone": zone}

    best = available[0]

    if best['percentage'] >= 50:
        emphasis = "most preferred location"
        detail = f"used for majority ({best['percentage']:.1f}%) of putaways"
    elif best['percentage'] >= 20:
        emphasis = "frequently used location"
        detail = f"commonly used ({best['percentage']:.1f}% of times)"
    elif best['count'] >= 5:
        emphasis = "historically used location"
        detail = f"previously used multiple times"
    else:
        emphasis = "available location from historical patterns"
        detail = "based on available historical data"

    prompt = (
        f"You are a warehouse management assistant. "
        f"Part '{part_code}' for client '{client_name}' needs to be stored in the warehouse. "
        f"Location '{best['code']}' is the {emphasis} for this part ({detail}) and is currently FREE and available for immediate use. "
        f"\n\nWrite a clear, confident recommendation in 1-2 sentences that: "
        f"1. States that location {best['code']} is recommended "
        f"2. Emphasizes it is FREE and ready to use RIGHT NOW "
        f"3. Mentions it follows historical patterns (without stating exact numbers) "
        f"Keep it professional and direct."
    )

    if best['percentage'] >= 30:
        fallback = (
            f"Location {best['code']} is recommended as it follows the established pattern for this part. "
            f"The location is currently FREE and ready for immediate use."
        )
    else:
        fallback = (
            f"Location {best['code']} is recommended based on historical usage patterns. "
            f"The location is currently FREE and available for use."
        )

    ai_text = call_gemini(model, prompt) or fallback

    audit_logger.log_recommendation(
        part_id=part_id,
        part_code=part_code,
        recommended_location=best['code'],
        status="FREE",
        usage_count=best['count'],
        usage_percentage=best['percentage'],
        alternatives=[a['code'] for a in available[1:4]]
    )

    logger.info(f"Recommendation generated for Part {part_code}: {best['code']}")

    return {
        **part_info,
        "status": "ok",
        "recommended": best,
        "alternatives": available[1:4],
        "all_available": available,
        "total_putaways": total_putaways,
        "ai_summary": ai_text,
    }

st.set_page_config(
    page_title="Putaway Recommendation",
    page_icon="📦",
    layout="wide",
)

st.markdown("""
<style>
    :root {
        --bg: #0f1217;
        --surface: #161b22;
        --surface-hover: #21262d;
        --text: #c9d1d9;
        --text-muted: #8b949e;
        --border: #30363d;
        --primary: #58a6ff;
        --success: #3fb950;
        --accent: #79c0ff;
    }

    .stApp { background-color: var(--bg) !important; }
    .main   { background-color: var(--bg) !important; color: var(--text) !important; }

    h1, h2, h3 { color: #ffffff !important; }

    .stTextInput > div > div > input {
        background-color: var(--surface) !important;
        color: var(--text) !important;
        border: 1px solid var(--border) !important;
        border-radius: 6px;
    }

    .stButton > button {
        background-color: #4b5563 !important;
        color: white !important;
        border: none !important;
        border-radius: 6px;
    }
    .stButton > button:hover {
        background-color: #374151 !important;
    }

    [data-testid="stMetric"] {
        background-color: var(--surface) !important;
        border: 1px solid var(--border) !important;
        border-radius: 8px;
        padding: 12px;
    }
    [data-testid="stMetricLabel"] { color: var(--text-muted) !important; }
    [data-testid="stMetricValue"] { color: #ffffff !important; font-size: 1.9rem !important; }

    hr { border-color: var(--border) !important; }

    .stAlert, .stInfo, .stWarning, .stSuccess {
        background-color: var(--surface) !important;
        border: 1px solid var(--border) !important;
        color: var(--text) !important;
        border-radius: 8px;
    }

    .recommendation-box {
        background: linear-gradient(145deg, #1a2338, #0f172a);
        border-left: 5px solid var(--success);
        padding: 1.8rem;
        border-radius: 8px;
        margin: 1.5rem 0;
        box-shadow: 0 4px 12px rgba(0,0,0,0.35);
    }

    .location-highlight {
        font-family: 'Courier New', monospace;
        font-size: 2.6rem;
        font-weight: bold;
        color: var(--accent);
        background: #0d1117;
        padding: 0.5rem 1rem;
        border-radius: 6px;
        border: 1px solid var(--border);
        display: inline-block;
    }

    .dataframe {
        background-color: var(--surface) !important;
    }
    .dataframe th {
        background-color: #21262d !important;
        color: white !important;
    }
    .dataframe td {
        color: var(--text) !important;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div style="text-align: center; padding: 2.2rem 0 1.4rem;">
    <h1 style="margin:0; font-size: 2.9rem;">📦 Putaway Recommendation</h1>
    <p style="color: #8b949e; font-size: 1.25rem; margin-top: 0.6rem;">
        Smart Location Assistant
    </p>
</div>
""", unsafe_allow_html=True)

st.markdown("### Enter Part ID")
c1, c2 = st.columns([5, 2])

with c1:
    part_id_str = st.text_input(
        "Part ID",
        placeholder="e.g. 600",
        label_visibility="collapsed",
        max_chars=12
    )

with c2:
    if st.button("Search", type="primary", use_container_width=True):
        try:
            pid = int(part_id_str.strip())
            with st.spinner("Generating recommendation..."):
                st.session_state.result = get_recommendation(pid)
                st.session_state.current_part_id = pid
        except ValueError:
            st.error("Part ID must be a valid number.")
        except Exception as e:
            st.error(f"Error: {str(e)}")
            logger.exception("Recommendation failed")

if 'result' in st.session_state and st.session_state.result:
    res = st.session_state.result

    if "error" in res:
        st.error(res["error"])
    else:
        st.markdown("### Part Details")
        cols = st.columns(4)
        cols[0].metric("Part ID", f"#{res['part_id']}")
        cols[1].metric("Code", res["part_code"])
        cols[2].metric("Client", res["client_name"])
        cols[3].metric("Description", res["description"][:40] + "…" if len(res["description"]) > 40 else res["description"])

        st.divider()

        if res["status"] == "no_history":
            st.warning("No historical putaway data available.")
            st.info(res["ai_summary"])
        elif res["status"] == "all_occupied":
            st.warning("All historical locations currently occupied.")
            st.info(res["ai_summary"])
        else:
            rec = res["recommended"]
            tot = res["total_putaways"]

            st.markdown(f"""
            <div class="recommendation-box">
                <h2 style="margin-top:0;">Recommended Location</h2>
                <div style="margin: 1.4rem 0;">
                    <span class="location-highlight">{rec['code']}</span>
                </div>
                <div style="display:flex; gap:2.5rem; flex-wrap:wrap; margin:1.6rem 0;">
                    <div>
                        <div style="color:#8b949e; font-size:0.95rem;">Status</div>
                        <div style="color:#3fb950; font-size:1.8rem; font-weight:600;">FREE</div>
                    </div>
                    <div>
                        <div style="color:#8b949e; font-size:0.95rem;">Historical Uses</div>
                        <div style="font-size:1.8rem; font-weight:600;">{rec['count']} × / {tot}</div>
                    </div>
                    <div>
                        <div style="color:#8b949e; font-size:0.95rem;">Usage Rate</div>
                        <div style="font-size:1.8rem; font-weight:600;">{rec['percentage']:.1f}%</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("### AI Recommendation")
            st.markdown(f"""
            <div style="background:#161b22; padding:1.4rem; border-radius:8px; border:1px solid #30363d; line-height:1.6;">
                {res['ai_summary']}
            </div>
            """, unsafe_allow_html=True)

            if res["alternatives"]:
                st.markdown("### Alternative Free Locations")
                alt_rows = [
                    {
                        "Rank": f"#{i+1}",
                        "Location": a["code"],
                        "Uses": f"{a['count']}×",
                        "%": f"{a['percentage']:.1f}%"
                    }
                    for i, a in enumerate(res["alternatives"])
                ]
                df_alt = pd.DataFrame(alt_rows)
                st.dataframe(
                    df_alt,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Rank": "Rank",
                        "Location": st.column_config.TextColumn("Location", width="medium"),
                        "Uses": "Times Used",
                        "%": st.column_config.NumberColumn("Usage %", format="%.1f%%"),
                    }
                )

            st.divider()

            st.subheader("Manual Override")
            c1, c2 = st.columns([3, 2])
            with c1:
                loc_input = st.text_input(
                    "Location code",
                    value=rec["code"],
                    help="Change only if necessary",
                    max_chars=20,
                    label_visibility="visible"
                )
            with c2:
                st.markdown("<div style='margin-top: 1.85rem;'></div>", unsafe_allow_html=True)
                if st.button("Confirm Putaway Location", type="primary", use_container_width=True):
                    chosen = (loc_input or "").strip().upper()
                    if not chosen:
                        st.warning("Please enter a location code.")
                    elif chosen == rec["code"]:
                        st.success(f"**{chosen}** confirmed (recommended location) ✓")
                    else:
                        audit_logger.log_override(
                            part_id=res["part_id"],
                            part_code=res["part_code"],
                            recommended_location=rec["code"],
                            actual_location=chosen,
                            reason="Manual override by user"
                        )
                        st.success(f"**{chosen}** confirmed (override)")
                        st.info("Override logged for audit.")