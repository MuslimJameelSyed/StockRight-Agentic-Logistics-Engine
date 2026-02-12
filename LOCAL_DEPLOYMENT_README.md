# Local Deployment - Quick Reference

All local deployment files have been organized into the **`local-deployment/`** folder.

---

## 📁 Folder Structure

```
warehouse-qdrant-system/
├── local-deployment/                      # ⭐ ALL LOCAL DEPLOYMENT FILES HERE
│   ├── README.md                          # Folder overview
│   ├── README_LOCAL.md                    # Quick start guide
│   ├── app_local.py                       # Streamlit web interface (local)
│   ├── warehouse_chat_local_ollama.py     # CLI interface (local)
│   ├── config_local.py                    # Local configuration
│   ├── docker-compose.yml                 # MySQL + Ollama containers
│   ├── .env.local.example                 # Environment template
│   ├── scripts/
│   │   ├── setup_local.bat               # Windows setup
│   │   └── setup_local.sh                # Linux/Mac setup
│   └── docs/
│       ├── LOCAL_DEPLOYMENT_GUIDE.md     # Comprehensive guide
│       └── DEPLOYMENT_SUMMARY.md         # Cloud vs Local comparison
│
├── app.py                                 # Cloud version (unchanged)
├── warehouse_chat_qdrant_llm.py          # Cloud CLI (unchanged)
├── config.py                              # Cloud config (unchanged)
├── error_handler.py                       # Shared utilities
├── requirements.txt                       # Shared dependencies
├── .env                                   # Your credentials (root)
└── README.md                              # Main documentation
```

---

## 🚀 Quick Start

### From `local-deployment` folder:

```bash
cd local-deployment

# 1. Setup (Windows)
scripts\setup_local.bat

# 1. Setup (Linux/Mac)
chmod +x scripts/setup_local.sh
./scripts/setup_local.sh

# 2. Run Web Interface
streamlit run app_local.py

# 3. Or run CLI
python warehouse_chat_local_ollama.py 600
```

---

## 📖 Documentation

**Start here:**
- **`local-deployment/README_LOCAL.md`** - Quick start guide

**Comprehensive info:**
- **`local-deployment/docs/LOCAL_DEPLOYMENT_GUIDE.md`** - Full deployment guide
- **`local-deployment/docs/DEPLOYMENT_SUMMARY.md`** - Cloud vs Local comparison

---

## ⚙️ Configuration

The `.env` file should remain in the **project root** (not in local-deployment folder).

Copy the local template and add your credentials:
```bash
cp local-deployment/.env.local.example .env
# Edit .env and add your Qdrant credentials
```

---

## 🔄 Switching Between Cloud and Local

### Cloud Version (Original)
```bash
# From project root:
streamlit run app.py
# or
python warehouse_chat_qdrant_llm.py 600
```

### Local Version (New)
```bash
# From local-deployment folder:
cd local-deployment
streamlit run app_local.py
# or
python warehouse_chat_local_ollama.py 600
```

### Run Both Simultaneously
```bash
# Terminal 1 (cloud) - from root:
streamlit run app.py

# Terminal 2 (local) - from local-deployment:
cd local-deployment
streamlit run app_local.py --server.port 8502
```

---

## 💰 Cost Comparison

| Component | Cloud | Local | Savings |
|-----------|-------|-------|---------|
| MySQL | $10-20/mo | $0 | $10-20/mo |
| AI/LLM | $20-50/mo | $0 | $20-50/mo |
| Qdrant | $0-20/mo | $0-20/mo | $0 |
| **Total** | **$30-90/mo** | **$5-30/mo** | **$20-60/mo** |

**Annual Savings: $240-720**

---

## 🔧 Key Files in `local-deployment/`

### Application Files
- **`app_local.py`** - Web interface with Ollama
- **`warehouse_chat_local_ollama.py`** - CLI with Ollama
- **`config_local.py`** - Local configuration (auto-loads from parent .env)

### Infrastructure
- **`docker-compose.yml`** - MySQL + Ollama containers
- **`.env.local.example`** - Environment variables template

### Setup Scripts
- **`scripts/setup_local.bat`** - Automated setup (Windows)
- **`scripts/setup_local.sh`** - Automated setup (Linux/Mac)

### Documentation
- **`README.md`** - Folder overview
- **`README_LOCAL.md`** - Quick start
- **`docs/LOCAL_DEPLOYMENT_GUIDE.md`** - Comprehensive guide (1,000+ lines)
- **`docs/DEPLOYMENT_SUMMARY.md`** - Comparison and analysis

---

## 📦 What's Included

### Local Deployment Uses:
1. **Qdrant Cloud API** - Same as cloud version (historical patterns)
2. **Local MySQL Docker** - Replaces Cloud SQL (real-time data)
3. **Local Ollama LLM** - Replaces Gemini API (AI recommendations)

### Benefits:
- ✅ Lower costs ($240-720/year savings)
- ✅ AI privacy (local inference)
- ✅ No rate limits (unlimited AI calls)
- ✅ Same Qdrant setup (no changes needed)

---

## 🐛 Common Issues

**Import errors:**
The `config_local.py` automatically handles parent directory imports. Just run scripts from the `local-deployment` folder.

**Docker not running:**
```bash
docker-compose up -d
docker ps
```

**Model not found:**
```bash
docker exec warehouse-ollama ollama pull llama3.2
```

**Can't connect to database:**
Check `.env` file exists in project root with correct credentials.

---

## 📚 Additional Resources

- Main project: `../README.md`
- Cloud setup: `../SETUP_GUIDE.md`
- Error handling: `../error_handler.py` (shared)
- Requirements: `../requirements.txt` (shared)

---

**All local deployment files are self-contained in the `local-deployment/` folder.**

**No changes to your existing cloud deployment!**
