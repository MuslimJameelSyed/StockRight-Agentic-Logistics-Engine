# Warehouse Putaway System - Setup Guide

Complete step-by-step instructions to run the Warehouse Putaway Recommendation System.

---

## 📋 Prerequisites

Before starting, ensure you have:
- **Python 3.9 or higher** installed
- **Git** installed
- Access to **Google Cloud SQL** (MySQL database)
- **Qdrant Cloud** account and API key
- **Google Gemini API** key

---

## 🚀 Installation Steps

### Step 1: Clone the Repository

```bash
git clone https://github.com/MuslimJameelSyed/Putaway-Agent-MVP.git
cd Putaway-Agent-MVP
```

### Step 2: Create Virtual Environment

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**macOS/Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Configure Environment Variables

1. **Copy the example file:**
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` with your credentials:**

   ```env
   # Database Configuration
   DB_HOST=your-cloud-sql-host
   DB_PORT=3306
   DB_USER=your-database-user
   DB_PASSWORD=your-database-password
   DB_NAME=your-database-name

   # Qdrant Configuration
   QDRANT_URL=https://your-qdrant-instance.cloud.qdrant.io:6333
   QDRANT_API_KEY=your-qdrant-api-key
   QDRANT_COLLECTION_NAME=PartSummary

   # Google Gemini AI
   GEMINI_API_KEY=your-gemini-api-key
   GEMINI_MODEL=gemini-2.0-flash-exp

   # Settings
   MAX_RETRIES=3
   LOG_LEVEL=INFO
   ```

   **Where to get API keys:**
   - **Qdrant**: [Qdrant Cloud Console](https://cloud.qdrant.io/) → Your Cluster → API Keys
   - **Gemini**: [Google AI Studio](https://makersuite.google.com/app/apikey) → Create API Key
   - **Cloud SQL**: Google Cloud Console → SQL → Your Instance → Credentials

### Step 5: Run the Application

```bash
streamlit run app.py
```

The app will open automatically at: **http://localhost:8501**

---

## 📱 How to Use

### 1. Search for a Part
- Enter the **Part ID** in the search box
- Click the **Search** button

### 2. View Recommendation
The system displays:
- ✅ Part details (ID, Code, Client, Description)
- ✅ Recommended location with historical usage
- ✅ AI-generated explanation
- ✅ Alternative free locations

### 3. Confirm or Override
- **Accept**: Keep the recommended location and click **"Confirm Putaway Location"**
- **Override**: Change the location code and click **"Confirm Putaway Location"**

---

## 🔧 Troubleshooting

### Database Connection Failed
- ✓ Verify Cloud SQL instance is running
- ✓ Check firewall rules allow your IP
- ✓ Confirm credentials in `.env`

### Qdrant Connection Failed
- ✓ Check Qdrant cluster is active
- ✓ Verify API key is correct
- ✓ Ensure URL includes port `:6333`

### Gemini API Unavailable
- ✓ Verify API key is valid
- ✓ Check API quota limits
- ✓ Confirm model name is correct

### Part Not Found
- ✓ Verify part exists in database
- ✓ Check part ID is correct

---

## 📊 System Components

1. **Qdrant** - Stores historical putaway patterns
2. **Cloud SQL** - Real-time location availability
3. **Gemini AI** - Generates natural language recommendations

**How it works:**
1. User enters Part ID
2. System retrieves historical data from Qdrant
3. Checks availability in Cloud SQL
4. AI generates recommendation
5. Displays result to user

---

## 📝 Important Notes

### Security
- ⚠️ **Never commit `.env` file** - Contains sensitive API keys
- 🔒 Keep API keys secure and private
- 🔄 Rotate keys regularly

### Logs
- Application logs: `logs/` directory
- Audit trail: `logs/audit.log` (tracks all confirmations and overrides)

---

## 🆘 Support

Check logs for errors:
```bash
cat logs/app.log
cat logs/audit.log
```

---

**Built with:** Streamlit • Qdrant • Cloud SQL • Google Gemini AI
