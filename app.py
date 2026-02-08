"""
Warehouse Putaway Recommendation - Streamlit App
Uses the same logic as warehouse_chat_qdrant_llm.py:
  - Qdrant for historical patterns
  - Cloud SQL for real-time location availability
  - Gemini for AI summaries

Production-ready with:
  - Environment variable configuration
  - Error handling and retry logic
  - Audit logging for compliance
"""

import streamlit as st
import mysql.connector
from qdrant_client import QdrantClient
import google.generativeai as genai
import logging

# Import configuration and error handling
from config import config, ConfigurationError
from error_handler import (
    retry_on_failure,
    audit_logger,
    DatabaseConnectionError,
    QdrantConnectionError,
    PartNotFoundError
)

# Setup logging
logger = logging.getLogger(__name__)

# ============================================================================
# CACHED CONNECTIONS WITH ERROR HANDLING
# ============================================================================

@st.cache_resource
def get_qdrant():
    """Get Qdrant client with error handling"""
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
    """Get MySQL connection with error handling"""
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
    """Get Gemini model with error handling"""
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

# ============================================================================
# HELPER FUNCTIONS (same logic as warehouse_chat_qdrant_llm.py)
# ============================================================================

def is_valid_location(location_code):
    if not location_code:
        return False
    if location_code.startswith(("FLOOR", "REC", "ORD")):
        return False
    if len(location_code) >= 2:
        last_two = location_code[-2:]
        if last_two.isalpha() and last_two[0] == last_two[1]:
            return False
    return True


def check_location_availability(location_code, cursor):
    cursor.execute("SELECT clientId FROM location WHERE code = %s", (location_code,))
    result = cursor.fetchone()
    if not result:
        return "UNKNOWN"
    return "FREE" if result[0] is None else "OCCUPIED"


@retry_on_failure(max_retries=config.MAX_RETRIES, delay=1.0)
def get_part_from_qdrant(qdrant, part_id):
    """Retrieve part from Qdrant with retry logic"""
    try:
        results = qdrant.retrieve(collection_name=config.QDRANT_COLLECTION_NAME, ids=[part_id])
        return results[0].payload if results else None
    except Exception as e:
        logger.error(f"Qdrant retrieval error for part {part_id}: {str(e)}")
        raise


def call_gemini(model, prompt):
    """Call Gemini and return text safely. Returns None on failure."""
    try:
        response = model.generate_content(
            prompt,
            generation_config={"temperature": 0.1, "max_output_tokens": 1024},
        )
        if (
            response.candidates
            and response.candidates[0].content
            and response.candidates[0].content.parts
        ):
            return response.candidates[0].content.parts[0].text
    except Exception:
        pass
    return None


# ============================================================================
# CORE RECOMMENDATION LOGIC
# ============================================================================

def get_recommendation(part_id: int):
    """
    Returns a dict with all recommendation data, or an error string.
    No print statements — everything returned for the UI to render.
    """
    qdrant = get_qdrant()
    db = get_db()
    model = get_gemini_model()

    # Reconnect if connection dropped
    if not db.is_connected():
        db.reconnect()

    cursor = db.cursor()

    # --- Part lookup ---
    cursor.execute("SELECT id, code, description, clientId FROM part WHERE id = %s", (part_id,))
    row = cursor.fetchone()
    if not row:
        cursor.close()
        return {"error": f"Part {part_id} not found in database."}

    _, part_code, description, client_id = row

    # --- Client name ---
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

    # --- Qdrant historical patterns ---
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

    # --- Filter & check availability ---
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

    # --- All occupied ---
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

    # --- Happy path: recommendation available ---
    best = available[0]
    prompt = (
        f"You are a warehouse management assistant. "
        f"Part '{part_code}' for client '{client_name}' needs to be stored in the warehouse. "
        f"IMPORTANT: This part was previously stored in location '{best['code']}' {best['count']} times "
        f"out of {total_putaways} total putaways ({best['percentage']:.1f}% of all times). "
        f"This location is currently FREE and available. "
        f"\n\nWrite a clear recommendation in 1-2 sentences that emphasizes: "
        f"'This part was historically put in {best['code']} [X times], so this is the best location to put it now.' "
        f"Keep it simple and direct."
    )
    ai_text = call_gemini(model, prompt) or (
        f"This part was historically stored in location {best['code']} {best['count']} times ({best['percentage']:.1f}%), "
        f"so this is the best location to put it. The location is currently FREE and ready for use."
    )

    # Log recommendation to audit trail
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
        "all_available": available,          # full list for the override dropdown
        "total_putaways": total_putaways,
        "ai_summary": ai_text,
    }


# ============================================================================
# STREAMLIT UI
# ============================================================================

st.set_page_config(
    page_title="Warehouse Putaway Recommendation",
    page_icon="🏭",
    layout="wide",
)

# Custom CSS for professional styling
st.markdown("""
<style>
    /* Main container styling */
    .main {
        background-color: #f8f9fa;
    }

    /* Header styling */
    .header-container {
        background: linear-gradient(135deg, #2980b9 0%, #3498db 100%);
        padding: 2rem;
        border-radius: 10px;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }

    .header-title {
        color: white;
        font-size: 2.5rem;
        font-weight: bold;
        margin: 0;
        text-align: center;
    }

    .header-subtitle {
        color: #ecf0f1;
        font-size: 1.1rem;
        text-align: center;
        margin-top: 0.5rem;
    }

    /* Card styling */
    .info-card {
        background: white;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        margin: 1rem 0;
    }

    /* Status badges */
    .status-badge-free {
        background-color: #27ae60;
        color: white;
        padding: 0.4rem 1rem;
        border-radius: 20px;
        font-weight: bold;
        display: inline-block;
    }

    .status-badge-occupied {
        background-color: #e74c3c;
        color: white;
        padding: 0.4rem 1rem;
        border-radius: 20px;
        font-weight: bold;
        display: inline-block;
    }

    /* Recommendation card */
    .recommendation-card {
        background: linear-gradient(135deg, #27ae60 0%, #2ecc71 100%);
        color: white;
        padding: 2rem;
        border-radius: 15px;
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.15);
        margin: 1.5rem 0;
    }

    .recommendation-title {
        font-size: 1.8rem;
        font-weight: bold;
        margin-bottom: 1rem;
    }

    /* Alternative card */
    .alternative-card {
        background: white;
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 4px solid #3498db;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        margin: 1rem 0;
    }

    /* Metric styling */
    div[data-testid="stMetricValue"] {
        font-size: 1.8rem;
        font-weight: bold;
    }

    /* Table styling */
    .dataframe {
        border-radius: 8px !important;
    }

    /* Warning/Info boxes */
    .stAlert {
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown("""
<div class="header-container">
    <h1 class="header-title">🏭 Warehouse Putaway System</h1>
    <p class="header-subtitle">AI-Powered Location Recommendations | Qdrant + Cloud SQL + Gemini</p>
</div>
""", unsafe_allow_html=True)

# Search section with better styling
st.markdown("### 🔍 Search for Part")
col1, col2 = st.columns([4, 1])

with col1:
    part_id_input = st.text_input(
        "Enter Part ID",
        placeholder="e.g. 600",
        max_chars=10,
        label_visibility="collapsed"
    )

with col2:
    search_btn = st.button("🔎 Search", type="primary", use_container_width=True)

if part_id_input or search_btn:
    # Validate input
    try:
        part_id = int(part_id_input.strip())
    except ValueError:
        st.error("⚠️ Part ID must be a number.")
        logger.warning(f"Invalid input: {part_id_input}")
        st.stop()

    try:
        with st.spinner("Looking up recommendation..."):
            result = get_recommendation(part_id)
    except QdrantConnectionError as e:
        st.error("🔴 Unable to connect to recommendation service (Qdrant). Please try again later.")
        logger.error(f"Qdrant connection failed: {str(e)}")
        audit_logger.log_error("QdrantConnectionError", str(e), part_id=part_id)
        st.stop()
    except DatabaseConnectionError as e:
        st.error("🔴 Unable to connect to database. Please try again later.")
        logger.error(f"Database connection failed: {str(e)}")
        audit_logger.log_error("DatabaseConnectionError", str(e), part_id=part_id)
        st.stop()
    except Exception as e:
        st.error(f"🔴 An unexpected error occurred: {str(e)}")
        logger.exception(f"Unexpected error for part {part_id}")
        audit_logger.log_error("UnexpectedError", str(e), part_id=part_id)
        st.stop()

    # --- Error ---
    if "error" in result:
        st.error(result["error"])
        st.stop()

    # --- Part info card ---
    st.markdown("### 📦 Part Information")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Part ID", f"#{result['part_id']}", help="Unique part identifier")
    with col2:
        st.metric("Part Code", result["part_code"], help="Part code in system")
    with col3:
        st.metric("Client", result["client_name"], help="Client owner")
    with col4:
        st.metric("Description", result["description"][:20] + "..." if len(result["description"]) > 20 else result["description"],
                  help=result["description"])

    # --- No history ---
    if result["status"] == "no_history":
        st.warning("No historical putaway data found for this part.")
        st.info(result["ai_summary"])
        st.stop()

    # --- All occupied ---
    if result["status"] == "all_occupied":
        st.warning("All historically used locations are currently occupied.")
        st.info(result["ai_summary"])
        st.stop()

    # --- Recommendation (happy path) ---
    rec = result["recommended"]
    total = result["total_putaways"]
    all_available = result["all_available"]

    st.divider()

    # Recommended location with styled card
    st.markdown("### ⭐ Recommended Location")

    # Create prominent recommendation card
    st.markdown(f"""
    <div class="recommendation-card">
        <div class="recommendation-title">📍 Location: {rec['code']}</div>
        <div style="display: flex; gap: 2rem; margin-top: 1rem;">
            <div style="flex: 1;">
                <div style="font-size: 0.9rem; opacity: 0.9;">Status</div>
                <div style="font-size: 1.5rem; font-weight: bold; margin-top: 0.3rem;">✓ FREE</div>
            </div>
            <div style="flex: 1;">
                <div style="font-size: 0.9rem; opacity: 0.9;">Historical Usage</div>
                <div style="font-size: 1.5rem; font-weight: bold; margin-top: 0.3rem;">{rec['count']}x / {total}</div>
            </div>
            <div style="flex: 1;">
                <div style="font-size: 0.9rem; opacity: 0.9;">Usage Rate</div>
                <div style="font-size: 1.5rem; font-weight: bold; margin-top: 0.3rem;">{rec['percentage']:.1f}%</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Alternatives table
    if result["alternatives"]:
        st.markdown("### 📋 Alternative Locations")
        import pandas as pd

        # Create better formatted table
        alt_data = []
        for i, a in enumerate(result["alternatives"], 1):
            alt_data.append({
                "Rank": f"#{i+1}",
                "Location": a["code"],
                "Usage Count": f"{a['count']}x",
                "Usage Rate": f"{a['percentage']:.1f}%",
                "Status": "✓ FREE"
            })

        df = pd.DataFrame(alt_data)
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Rank": st.column_config.TextColumn("Rank", width="small"),
                "Location": st.column_config.TextColumn("Location Code", width="medium"),
                "Usage Count": st.column_config.TextColumn("Times Used", width="medium"),
                "Usage Rate": st.column_config.TextColumn("Usage %", width="medium"),
                "Status": st.column_config.TextColumn("Availability", width="medium"),
            }
        )

    # AI Summary
    st.divider()
    st.markdown("### 🤖 AI Explanation")
    st.markdown(f"""
    <div class="info-card">
        <div style="font-size: 1.1rem; line-height: 1.6; color: #2c3e50;">
            {result["ai_summary"]}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # --- Human Override (bottom) ---
    st.divider()
    st.markdown("### 🔄 Override Recommendation")
    st.markdown("Choose a different location if needed. All options shown are currently FREE.")

    col1, col2 = st.columns([3, 1])

    with col1:
        override_options = ["— Use Recommended Location —"] + [
            f"{loc['code']} (used {loc['count']}x, {loc['percentage']:.1f}%)" for loc in all_available
        ]
        override_choice = st.selectbox(
            "Select Location:",
            options=override_options,
            help="All locations shown are verified as FREE in real-time"
        )

    with col2:
        confirm_btn = st.button("✓ Confirm Selection", type="primary", use_container_width=True)

    if override_choice != "— Use Recommended Location —":
        # Extract location code from formatted string
        chosen_code = override_choice.split(" (")[0]
        chosen = next((loc for loc in all_available if loc["code"] == chosen_code), None)

        if chosen:
            st.markdown(f"""
            <div class="alternative-card">
                <div style="font-size: 1.3rem; font-weight: bold; color: #3498db; margin-bottom: 0.5rem;">
                    📍 Selected: {chosen_code}
                </div>
                <div style="display: flex; gap: 2rem;">
                    <div>
                        <span style="color: #7f8c8d;">Status:</span>
                        <span style="color: #27ae60; font-weight: bold;"> ✓ FREE</span>
                    </div>
                    <div>
                        <span style="color: #7f8c8d;">Historical Usage:</span>
                        <span style="font-weight: bold;"> {chosen['count']}x / {total} ({chosen['percentage']:.1f}%)</span>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            if confirm_btn:
                # Log override to audit trail
                audit_logger.log_override(
                    part_id=result['part_id'],
                    part_code=result['part_code'],
                    recommended_location=rec['code'],
                    actual_location=chosen_code,
                    reason="User selected alternative location"
                )
                logger.warning(f"Override: Part {result['part_code']} - Recommended {rec['code']}, User chose {chosen_code}")
                st.success(f"✓ Location {chosen_code} confirmed! Proceed with putaway.")
    else:
        if confirm_btn:
            logger.info(f"Confirmed: Part {result['part_code']} - Location {rec['code']}")
            st.success(f"✓ Recommended location {rec['code']} confirmed! Proceed with putaway.")
