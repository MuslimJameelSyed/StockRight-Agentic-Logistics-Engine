# Warehouse Putaway System - Local Deployment

**Quick Start Guide for Local RAG-Based AI System**

---

## Overview

This is the **local deployment version** of the Warehouse Putaway Recommendation System. It uses:

- **Qdrant Cloud API** (vector database - your existing setup)
- **Local MySQL** (Docker container - no Cloud SQL costs)
- **Local Ollama** (LLM - no Gemini API costs)

**Estimated Setup Time:** 15-30 minutes

---

## Quick Start (5 Steps)

### 1. Prerequisites

Make sure you have installed:
- **Docker Desktop** - https://www.docker.com/products/docker-desktop
- **Python 3.12+** - https://www.python.org/downloads/
- **Git** - https://git-scm.com/downloads

### 2. Clone & Configure

```bash
# Clone the repository
git clone https://github.com/your-org/warehouse-qdrant-system.git
cd warehouse-qdrant-system

# Copy environment template
cp .env.local.example .env

# Edit .env and add your Qdrant credentials
# (You already have these from your cloud setup)
```

### 3. Start Docker Services

```bash
# Start MySQL + Ollama containers
docker-compose up -d

# Wait 30 seconds for MySQL to initialize
```

### 4. Download AI Model

```bash
# Download Llama 3.2 model (one-time download, ~3GB)
docker exec warehouse-ollama ollama pull llama3.2
```

### 5. Run the System

```bash
# Install Python dependencies
pip install -r requirements.txt

# Run web interface
streamlit run app.py

# Or run CLI version
python warehouse_cli.py 600
```

Done! The system is now running at **http://localhost:8501**

---

## What's Different from Cloud Version?

| Feature | Cloud Version | Local Version |
|---------|--------------|---------------|
| **Vector DB** | Qdrant Cloud API | Qdrant Cloud API (same) |
| **SQL Database** | Cloud SQL ($10-20/mo) | Local MySQL Docker (free) |
| **AI Model** | Google Gemini ($20-50/mo) | Local Ollama (free) |
| **Monthly Cost** | $30-90 | $0-5 (electricity only) |
| **Internet Required** | Yes (for Qdrant + Gemini) | Minimal (only for Qdrant) |
| **AI Privacy** | Cloud-based reasoning | Local reasoning |
| **Setup Complexity** | Simple (no Docker) | Moderate (Docker required) |

---

## Architecture

```
┌─────────────────────────────────────┐
│         USER INTERFACE              │
│   (Streamlit Web or CLI)            │
└──────────────┬──────────────────────┘
               │
               v
┌──────────────────────────────────────┐
│       APPLICATION LAYER              │
│      (Python + config.py)      │
└────┬───────────────────┬─────────────┘
     │                   │
     v                   v
┌─────────────┐    ┌─────────────┐
│   Qdrant    │    │   MySQL     │
│ Cloud API   │    │  (Docker)   │
│  (Patterns) │    │(Availability)│
└──────┬──────┘    └──────┬──────┘
       │                  │
       └──────┬───────────┘
              v
      ┌───────────────┐
      │Context Engine │
      │  (Retrieval)  │
      └───────┬───────┘
              v
      ┌───────────────┐
      │ Ollama LLM    │
      │   (Docker)    │
      │  (Generate)   │
      └───────────────┘
```

---

## File Guide

### Local Deployment Files (New)

- **`app.py`** - Streamlit web interface (local version)
- **`warehouse_cli.py`** - CLI interface (local version)
- **`config.py`** - Local configuration module
- **`docker-compose.yml`** - MySQL + Ollama containers
- **`LOCAL_DEPLOYMENT_GUIDE.md`** - Full deployment guide
- **`.env.local.example`** - Environment variables template

### Original Cloud Files (Unchanged)

- **`app.py`** - Streamlit web interface (cloud version)
- **`warehouse_chat_qdrant_llm.py`** - CLI interface (cloud version)
- **`config.py`** - Cloud configuration module

### Shared Files

- **`error_handler.py`** - Error handling and audit logging
- **`requirements.txt`** - Python dependencies (supports both versions)
- **`.env`** - Environment variables (your credentials)

---

## Common Commands

### Start/Stop Services

```bash
# Start all containers
docker-compose up -d

# Stop all containers
docker-compose down

# Restart containers
docker-compose restart

# View container status
docker ps

# View logs
docker-compose logs
docker logs warehouse-mysql
docker logs warehouse-ollama
```

### Model Management

```bash
# List downloaded models
docker exec warehouse-ollama ollama list

# Download a model
docker exec warehouse-ollama ollama pull llama3.2
docker exec warehouse-ollama ollama pull mistral
docker exec warehouse-ollama ollama pull phi3

# Remove a model
docker exec warehouse-ollama ollama rm llama3.2
```

### Database Management

```bash
# Backup MySQL database
docker exec warehouse-mysql mysqldump -uroot -pwarehouse_root_2024 \
  mydatabase_gdpr > backup_$(date +%Y%m%d).sql

# Restore MySQL database
docker exec -i warehouse-mysql mysql -uroot -pwarehouse_root_2024 \
  mydatabase_gdpr < backup.sql

# Connect to MySQL shell
docker exec -it warehouse-mysql mysql -uroot -pwarehouse_root_2024
```

---

## Troubleshooting

### Issue: Containers won't start

```bash
# Check Docker is running
docker ps

# Check port conflicts (3306, 11434)
netstat -an | grep 3306
netstat -an | grep 11434

# View logs
docker-compose logs
```

### Issue: Model not found

```bash
# Download the model
docker exec warehouse-ollama ollama pull llama3.2

# Verify it's downloaded
docker exec warehouse-ollama ollama list
```

### Issue: Python import errors

```bash
# Reinstall dependencies
pip install -r requirements.txt

# Verify config loads
python -c "from config_local import config_local; print('OK')"
```

### Issue: Qdrant connection failed

```bash
# Check .env file has Qdrant credentials
cat .env | grep QDRANT

# Test Qdrant connection
curl https://your-qdrant-url.cloud.qdrant.io
```

---

## Performance Tuning

### Faster Responses

Use a smaller, faster model:

```bash
# Download phi3 (2GB, faster than llama3.2)
docker exec warehouse-ollama ollama pull phi3

# Update .env
OLLAMA_MODEL=phi3
```

### Better Quality

Use a larger, more capable model:

```bash
# Download mistral (4GB, better quality)
docker exec warehouse-ollama ollama pull mistral

# Update .env
OLLAMA_MODEL=mistral
```

### Resource Management

Increase Docker resources in Docker Desktop:
- Settings → Resources → Advanced
- Increase Memory to 8+ GB
- Increase CPUs to 4+ cores

---

## Cost Savings

### Monthly Comparison

| Service | Cloud Cost | Local Cost | Savings |
|---------|------------|------------|---------|
| MySQL Database | $10-20 | $0 | $10-20 |
| Gemini AI | $20-50 | $0 | $20-50 |
| Qdrant | $0-20 | $0-20 | $0 |
| Electricity | - | $5-10 | -$5-10 |
| **Total** | **$30-90** | **$5-30** | **$20-60** |

**Annual Savings:** $240-$720 per year

---

## Security Notes

**Default Passwords:**
The `.env.local.example` file contains default passwords. **Change these before production use!**

```bash
# Edit .env and change:
MYSQL_PASSWORD=your-strong-password-here
MYSQL_ROOT_PASSWORD=your-strong-root-password-here
```

**Data Privacy:**
- Qdrant queries: Cloud API (encrypted, historical patterns only)
- MySQL data: Local only (never leaves your server)
- AI inference: Local only (never sent to cloud)
- Recommendations: Generated locally

---

## Support

**For detailed information, see:**
- **LOCAL_DEPLOYMENT_GUIDE.md** - Complete deployment guide
- **SETUP_GUIDE.md** - Original cloud setup guide
- **README.md** - Main project documentation

**Check logs:**
```bash
# Application logs
tail -f logs/audit.log

# Docker logs
docker-compose logs -f
```

**Verify system health:**
```bash
# Check all containers
docker ps

# Test database connection
docker exec warehouse-mysql mysql -uroot -pwarehouse_root_2024 -e "SELECT 1;"

# Test Ollama
curl http://localhost:11434/api/tags
```

---

## Next Steps

1. **Read the full guide:** See `LOCAL_DEPLOYMENT_GUIDE.md` for comprehensive documentation
2. **Import your data:** If you have a MySQL backup, import it
3. **Test the system:** Try a few part lookups
4. **Monitor performance:** Check Docker resource usage with `docker stats`
5. **Set up backups:** Schedule regular MySQL backups

---

**Version:** 1.0 (Local Deployment)
**Last Updated:** February 2026
**System:** Hybrid RAG - Cloud Vector DB + Local Compute
