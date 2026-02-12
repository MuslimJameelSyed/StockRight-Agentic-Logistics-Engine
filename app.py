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
def get_db_pool():
    """Create a connection pool instead of a single connection"""
    try:
        logger.info("Initializing Cloud SQL connection pool...")
        from mysql.connector import pooling

        db_config = config.get_db_config()
        pool = pooling.MySQLConnectionPool(
            pool_name="streamlit_pool",
            pool_size=5,
            pool_reset_session=True,
            **db_config
        )
        logger.info("Cloud SQL connection pool established")
        return pool
    except Exception as e:
        logger.error(f"Failed to create connection pool: {str(e)}")
        raise DatabaseConnectionError(f"Could not create database pool: {str(e)}")

def get_db_connection():
    """Get a fresh connection from the pool with automatic retry"""
    pool = get_db_pool()
    try:
        conn = pool.get_connection()
        if not conn.is_connected():
            conn.reconnect(attempts=3, delay=1)
        return conn
    except Exception as e:
        logger.error(f"Failed to get connection from pool: {str(e)}")
        raise DatabaseConnectionError(f"Could not get database connection: {str(e)}")

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
    model = get_gemini_model()

    # Get a fresh connection from the pool
    db = get_db_connection()
    cursor = None

    try:
        cursor = db.cursor()

        cursor.execute("SELECT id, code, description, clientId FROM part WHERE id = %s", (part_id,))
        row = cursor.fetchone()
        if not row:
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
    finally:
        # Always close cursor and connection
        if cursor:
            cursor.close()
        if db:
            db.close()

st.set_page_config(
    page_title="StockRight - RAG Putaway System",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header[data-testid="stHeader"] {visibility: hidden;}

    /* Main container */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1400px;
    }

    /* Header */
    .main-header {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
        padding: 2rem 2.5rem;
        border-radius: 12px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15);
    }

    .main-header h1 {
        margin: 0;
        font-size: 2.5rem;
        font-weight: 700;
        letter-spacing: -0.5px;
    }

    .main-header p {
        margin: 0.5rem 0 0 0;
        font-size: 1.1rem;
        opacity: 0.95;
    }

    .status-badge {
        display: inline-block;
        background: rgba(255,255,255,0.2);
        padding: 0.3rem 1rem;
        border-radius: 20px;
        font-size: 0.85rem;
        margin-top: 0.8rem;
    }

    /* Cards */
    .card {
        background: #ffffff;
        padding: 1.8rem;
        border-radius: 12px;
        box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
        border: 1px solid #e8e8e8;
        height: 100%;
        margin-bottom: 1rem;
    }

    .card-header {
        font-size: 1.2rem;
        font-weight: 600;
        color: #1e3c72;
        margin-bottom: 1.2rem;
        padding-bottom: 0.8rem;
        border-bottom: 2px solid #1e3c72;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }

    /* Location Display */
    .location-display {
        background: linear-gradient(135deg, #00b09b 0%, #96c93d 100%);
        color: white;
        padding: 2rem;
        border-radius: 12px;
        text-align: center;
        margin: 1.5rem 0;
        box-shadow: 0 6px 20px rgba(0, 176, 155, 0.3);
    }

    .location-label {
        font-size: 0.9rem;
        opacity: 0.9;
        text-transform: uppercase;
        letter-spacing: 1px;
    }

    .location-code {
        font-size: 3.5rem;
        font-weight: 800;
        margin: 0.5rem 0;
        text-shadow: 0 2px 4px rgba(0,0,0,0.1);
        font-family: 'Courier New', monospace;
    }

    .location-status {
        font-size: 1.2rem;
        opacity: 0.95;
        font-weight: 600;
    }

    /* Badges */
    .badge {
        display: inline-block;
        padding: 0.5rem 1.2rem;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.85rem;
        margin: 0.3rem;
    }

    .badge-high { background: #d4edda; color: #155724; }
    .badge-medium { background: #fff3cd; color: #856404; }
    .badge-low { background: #f8d7da; color: #721c24; }
    .badge-info { background: #1e3c72; color: white; }

    /* Stats Box */
    .stats-box {
        background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
        padding: 1.2rem;
        border-radius: 10px;
        border-left: 4px solid #1e3c72;
        margin: 1rem 0;
    }

    .stats-row {
        display: flex;
        justify-content: space-between;
        padding: 0.5rem 0;
        border-bottom: 1px solid #dee2e6;
    }

    .stats-row:last-child { border-bottom: none; }
    .stats-label { font-weight: 600; color: #495057; }
    .stats-value { color: #212529; }

    /* AI Reasoning Box */
    .ai-reasoning {
        background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%);
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 4px solid #2196f3;
        margin: 1rem 0;
        font-size: 0.95rem;
        line-height: 1.7;
        color: #1565c0;
    }

    /* Alternative Locations */
    .alt-location {
        background: #f8f9fa;
        padding: 0.8rem 1rem;
        margin: 0.5rem 0;
        border-radius: 8px;
        border-left: 3px solid #6c757d;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    .alt-location:hover {
        background: #e9ecef;
        transform: translateX(5px);
        transition: all 0.2s ease;
    }

    /* Buttons */
    .stButton > button {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%) !important;
        color: white !important;
        border: none !important;
        padding: 0.75rem 2rem !important;
        font-size: 1rem !important;
        font-weight: 600 !important;
        border-radius: 8px !important;
        box-shadow: 0 4px 12px rgba(30, 60, 114, 0.3) !important;
        transition: all 0.3s ease !important;
        width: 100% !important;
    }

    .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(30, 60, 114, 0.4) !important;
    }

    /* Metrics */
    [data-testid="stMetric"] {
        background-color: #f8f9fa !important;
        border: 1px solid #dee2e6 !important;
        border-radius: 8px !important;
        padding: 1rem !important;
    }

    [data-testid="stMetricLabel"] {
        color: #6c757d !important;
        font-weight: 600 !important;
    }

    [data-testid="stMetricValue"] {
        color: #212529 !important;
        font-size: 1.8rem !important;
        font-weight: 700 !important;
    }

    /* Input fields */
    .stTextInput > div > div > input {
        border: 2px solid #dee2e6 !important;
        border-radius: 8px !important;
        padding: 0.75rem !important;
        font-size: 1rem !important;
    }

    .stTextInput > div > div > input:focus {
        border-color: #1e3c72 !important;
        box-shadow: 0 0 0 0.2rem rgba(30, 60, 114, 0.25) !important;
    }

    .stTextInput > label {
        font-weight: 600 !important;
        color: #495057 !important;
    }

    /* Dataframe */
    .dataframe {
        border: none !important;
    }

    .dataframe th {
        background-color: #1e3c72 !important;
        color: white !important;
        font-weight: 600 !important;
        padding: 0.75rem !important;
    }

    .dataframe td {
        padding: 0.75rem !important;
        border-bottom: 1px solid #dee2e6 !important;
    }

    /* Divider */
    hr {
        margin: 2rem 0 !important;
        border-color: #dee2e6 !important;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="main-header">
    <h1>🏭 STOCKRIGHT RAG PUTAWAY SYSTEM</h1>
    <p>Real-time intelligent location recommendations powered by RAG architecture</p>
    <div class="status-badge">🤖 Qdrant • Cloud SQL • Gemini AI</div>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="card">
    <div class="card-header">📦 Part Lookup</div>
</div>
""", unsafe_allow_html=True)

c1, c2 = st.columns([5, 2])

with c1:
    part_id_str = st.text_input(
        "Part ID",
        placeholder="e.g. 600",
        label_visibility="collapsed",
        max_chars=12
    )

with c2:
    st.markdown("<div style='margin-top: 1.6rem;'></div>", unsafe_allow_html=True)
    if st.button("🚀 GET RECOMMENDATION", type="primary", use_container_width=True):
        try:
            pid = int(part_id_str.strip())
            with st.spinner("🔄 Analyzing historical patterns via RAG..."):
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
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("""
        <div class="card">
            <div class="card-header">📋 Part Details</div>
        </div>
        """, unsafe_allow_html=True)

        cols = st.columns(4)
        cols[0].metric("Part ID", f"#{res['part_id']}")
        cols[1].metric("Code", res["part_code"])
        cols[2].metric("Client", res["client_name"])
        cols[3].metric("Description", res["description"][:40] + "…" if len(res["description"]) > 40 else res["description"])

        st.divider()

        if res["status"] == "no_history":
            st.warning("⚠️ No historical putaway data available.")
            st.info(res["ai_summary"])
        elif res["status"] == "all_occupied":
            st.warning("⚠️ All historical locations currently occupied.")
            st.info(res["ai_summary"])
        else:
            rec = res["recommended"]
            tot = res["total_putaways"]

            # Main Recommendation Card
            st.markdown(f"""
            <div class="location-display">
                <div class="location-label">✨ Recommended Location</div>
                <div class="location-code">{rec['code']}</div>
                <div class="location-status">🟢 FREE & READY FOR USE</div>
            </div>
            """, unsafe_allow_html=True)

            # Stats Box
            st.markdown(f"""
            <div class="stats-box">
                <div class="stats-row">
                    <span class="stats-label">📊 Historical Uses</span>
                    <span class="stats-value">{rec['count']} times (out of {tot} total)</span>
                </div>
                <div class="stats-row">
                    <span class="stats-label">📈 Usage Rate</span>
                    <span class="stats-value">{rec['percentage']:.1f}%</span>
                </div>
                <div class="stats-row">
                    <span class="stats-label">✅ Status</span>
                    <span class="stats-value" style="color: #28a745; font-weight: 700;">FREE</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # AI Reasoning
            st.markdown("""
            <div class="card">
                <div class="card-header">🤖 AI-Generated Reasoning</div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown(f"""
            <div class="ai-reasoning">
                <strong>🧠 Gemini AI Analysis:</strong><br><br>
                {res['ai_summary']}
            </div>
            """, unsafe_allow_html=True)

            # Confidence Badge
            confidence_level = "HIGH" if rec['percentage'] >= 30 else "MEDIUM" if rec['percentage'] >= 15 else "LOW"
            badge_class = "badge-high" if rec['percentage'] >= 30 else "badge-medium" if rec['percentage'] >= 15 else "badge-low"
            st.markdown(f"""
            <div style="text-align: center; margin: 1rem 0;">
                <span class="badge {badge_class}">⚡ {confidence_level} CONFIDENCE</span>
                <span class="badge badge-info">🔄 RAG Pipeline</span>
            </div>
            """, unsafe_allow_html=True)

            # Alternative Locations
            if res["alternatives"]:
                st.markdown("<br>", unsafe_allow_html=True)
                st.markdown("""
                <div class="card">
                    <div class="card-header">🔄 Alternative Free Locations</div>
                </div>
                """, unsafe_allow_html=True)

                for i, alt in enumerate(res["alternatives"]):
                    st.markdown(f"""
                    <div class="alt-location">
                        <span><strong>#{i+2}</strong> - {alt['code']}</span>
                        <span style="color: #6c757d;">Used {alt['count']}× ({alt['percentage']:.1f}%)</span>
                    </div>
                    """, unsafe_allow_html=True)

            st.divider()

            # Human Override Section
            st.markdown("""
            <div class="card">
                <div class="card-header">👤 Human-in-the-Loop Confirmation</div>
            </div>
            """, unsafe_allow_html=True)

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
                if st.button("✓ CONFIRM PUTAWAY", type="primary", use_container_width=True):
                    chosen = (loc_input or "").strip().upper()
                    if not chosen:
                        st.warning("Please enter a location code.")
                    elif chosen == rec["code"]:
                        st.success(f"✅ **{chosen}** confirmed (recommended location)")
                        st.balloons()
                    else:
                        audit_logger.log_override(
                            part_id=res["part_id"],
                            part_code=res["part_code"],
                            recommended_location=rec["code"],
                            actual_location=chosen,
                            reason="Manual override by user"
                        )
                        st.success(f"✅ **{chosen}** confirmed (override)")
                        st.info("📝 Override logged for audit and pattern learning.")