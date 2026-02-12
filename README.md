# Warehouse Putaway Recommendation System (API-Based)

🏭 **Production-Ready** API-based warehouse putaway system using Cloud SQL, Qdrant Vector DB, and Google Gemini AI.

## 🌐 Live Demo

**Try it now:** [https://stockright.streamlit.app/](https://stockright.streamlit.app/)

Experience the system live with real warehouse data and AI-powered recommendations.

---

## System Overview

This API-based system recommends optimal storage locations for incoming warehouse inventory using **RAG (Retrieval-Augmented Generation)** architecture:
- **Qdrant Cloud API** - Vector database for historical putaway patterns (Retrieval)
- **Google Cloud SQL API** - Real-time location availability via MySQL (Augmentation)
- **Google Gemini API** - AI-powered natural language explanations (Generation)

## Core Applications

### 1. Web Interface (Streamlit)
```bash
streamlit run app.py
```
Modern web UI for warehouse operators to get putaway recommendations.

### 2. Command Line Interface
```bash
python warehouse_chat_qdrant_llm.py 600
```
Terminal-based recommendations with interactive mode.

## How It Works

**RAG-Powered Three-Step Process:**
1. **Retrieval:** Query historical patterns from Qdrant vector database
2. **Augmentation:** Check real-time location availability in Cloud SQL
3. **Generation:** AI-powered explanation using Google Gemini

**Recommendation Strategy:**
- Use historical putaway patterns (most frequently used locations)
- Verify locations are FREE (clientId = NULL in database)
- Filter out invalid locations (FLOOR*, REC*, ORD*, subdivisions)
- Provide alternatives and confidence scores

## Installation

### Requirements
- Python 3.8+
- Qdrant Cloud account
- Google Cloud SQL (MySQL)
- Google Gemini API key

### Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment (optional)
cp .env.example .env
# Edit .env with your credentials
```

## Configuration

The system uses `config.py` for centralized configuration with fallback defaults:
- Qdrant connection (vector database)
- Cloud SQL credentials (MySQL)
- Gemini API key (AI)

You can override defaults using a `.env` file.

## Key Features

### Core Functionality
✓ Historical pattern analysis from Qdrant
✓ Real-time availability checking
✓ AI-powered explanations (improved clarity)
✓ Location validation and filtering
✓ Alternative recommendations
✓ User override capability (web UI)

### Production Features
✓ **Secure:** Environment-based credentials (no hardcoded secrets)
✓ **Reliable:** Automatic retry logic for transient failures
✓ **Auditable:** Complete logging of all recommendations and overrides
✓ **Error Handling:** User-friendly error messages, graceful degradation

## Example Usage

**Question:** "Where should I put Part 600?"

**Response:**
```
RECOMMENDED LOCATION: TN52D
Status: FREE (clientId = NULL)
Historical Usage: 15x out of 53 putaways (28.3%)

AI Summary: Location TN52D is recommended because it has been
used 15 times (28.3%) for this part historically and is currently
FREE and available for use.

ALTERNATIVES:
1. SG01J - 8x (15.1%) - FREE
2. TP03D - 3x (5.66%) - FREE
```

## Architecture

```
User Request → Qdrant (historical data) → Cloud SQL (availability) → Gemini AI (explanation) → Recommendation
```

## Files

### Core Application
- `app.py` - Streamlit web interface
- `warehouse_chat_qdrant_llm.py` - CLI interface
- `config.py` - Configuration management
- `error_handler.py` - Error handling and audit logging
- `requirements.txt` - Python dependencies

### Configuration
- `.env.example` - Environment variables template
- `.gitignore` - Git ignore rules

### Documentation
- `README.md` - System overview and usage
- `SETUP_GUIDE.md` - Step-by-step installation guide

---

## 📊 Audit Logging

All system events are logged to `logs/audit.log` in JSON format:

**Recommendations:**
```json
{"event_type": "recommendation", "part_code": "42645EQ", "recommended_location": "TP49A", ...}
```

**Overrides:**
```json
{"event_type": "override", "recommended_location": "TP49A", "actual_location": "TN43D", ...}
```

**Errors:**
```json
{"event_type": "error", "error_type": "DatabaseConnectionError", ...}
```

---

## 🚀 Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure credentials:**
   ```bash
   # .env file is already configured
   # Or copy template: cp .env.example .env
   ```

3. **Run web app:**
   ```bash
   streamlit run app.py
   ```

4. **Monitor logs:**
   ```bash
   tail -f logs/audit.log
   ```
