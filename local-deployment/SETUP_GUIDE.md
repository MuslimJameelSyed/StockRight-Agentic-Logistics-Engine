# Setup Guide - Warehouse Putaway System

Complete setup instructions for running the system from GitHub.

---

## System Overview

Recommends optimal warehouse locations for storing parts based on:
- **Historical patterns** from Qdrant vector database
- **Current availability** from MySQL database
- **AI explanations** from local Ollama LLM

### Architecture

```
User Input (Part ID)
       ↓
┌─────────────────────┐
│ Qdrant Cloud API    │ → Historical putaway patterns
└─────────────────────┘
       ↓
┌─────────────────────┐
│ MySQL (Docker)      │ → Check FREE/OCCUPIED status
└─────────────────────┘
       ↓
┌─────────────────────┐
│ Ollama (Docker)     │ → Generate explanation
└─────────────────────┘
       ↓
Recommendation Output
```

---

## Installation Steps

### Step 1: Clone Repository

```bash
git clone <repository-url>
cd local-deployment
```

### Step 2: Install Prerequisites

**Required:**
- Docker Desktop: https://www.docker.com/products/docker-desktop
- Python 3.8+: https://www.python.org/downloads/

**Verify:**
```bash
docker --version
python --version
```

### Step 3: Configure Qdrant

Edit `.env` file:

```env
QDRANT_URL=https://your-cluster.cloud.qdrant.io
QDRANT_API_KEY=your-api-key-here
```

### Step 4: Start Services

```bash
# Start Docker containers
docker-compose up -d

# Download AI model (~2GB, 5-10 minutes)
docker exec warehouse-ollama ollama pull llama3.2

# Install Python dependencies
pip install -r requirements.txt
```

### Step 5: Run the System

**Web Interface:**
```bash
streamlit run app.py
```
Open: http://localhost:8501

**Command Line:**
```bash
python warehouse_cli.py 600
```

---

## Key Concepts

### 1. Qdrant (Historical Patterns)
- Vector database storing historical putaway patterns
- Cloud API (requires internet)
- Example: Part 600 → TP49A used 2 times (3.8% of 53 putaways)

### 2. MySQL (Current Availability)
- Relational database with real-time location status
- Local Docker container (port 3307)
- Data: 87 clients, 3,215 parts, 31,416 locations
- Status: FREE (clientId=NULL) or OCCUPIED (clientId=value)

### 3. Ollama (AI Explanations)
- Local LLM for natural language generation
- Docker container (port 11434)
- Model: llama3.2 (~2GB)

### 4. Recommendation Logic

```python
# 1. Get historical patterns from Qdrant
historical_locations = qdrant.get_patterns(part_id=600)
# Result: [TP49A: 2x, TN43D: 1x, TN49B: 1x]

# 2. Check availability in MySQL
for location in historical_locations:
    status = mysql.check(location)
    # TP49A: FREE
    # TN43D: FREE

# 3. Pick best FREE location (highest historical usage)
recommended = "TP49A"  # Used 2x, currently FREE

# 4. Generate AI explanation with Ollama
explanation = ollama.generate(f"Recommend {recommended} for Part 600")
```

---

## File Structure

```
local-deployment/
├── .env                    # Configuration (UPDATE THIS!)
├── docker-compose.yml      # Docker services
├── config.py               # Config loader
├── warehouse_cli.py        # CLI application
├── app.py                  # Web UI
├── requirements.txt        # Python packages
├── data/                   # Auto-imported SQL files
│   ├── client.sql          # 87 clients
│   ├── part.sql            # 3,215 parts
│   ├── location.sql        # 31,416 locations
│   └── import_all.sql      # Import script
├── README.md               # Main documentation
└── SETUP_GUIDE.md          # This file
```

---

## Configuration

### Environment Variables

```env
# Qdrant Cloud API
QDRANT_URL=https://your-cluster.cloud.qdrant.io
QDRANT_API_KEY=your-api-key
QDRANT_COLLECTION_NAME=PartSummary

# Local MySQL
MYSQL_HOST=localhost
MYSQL_PORT=3307
MYSQL_DATABASE=mydatabase_gdpr
MYSQL_USER=muslim
MYSQL_PASSWORD=warehouse_pass_2024

# Local Ollama
OLLAMA_HOST=localhost
OLLAMA_PORT=11434
OLLAMA_MODEL=llama3.2
OLLAMA_TEMPERATURE=0.1
OLLAMA_MAX_TOKENS=1024

# Application
LOG_LEVEL=INFO
ENABLE_AUDIT_LOG=true
MAX_RETRIES=3
REQUEST_TIMEOUT=30
```

---

## Database

### Auto-Import

MySQL container automatically imports on first start:

| File           | Records | Description                    |
|----------------|---------|--------------------------------|
| client.sql     | 87      | Client information             |
| part.sql       | 3,215   | Part catalog                   |
| location.sql   | 31,416  | Warehouse locations with status|

**Location Status:**
- `clientId = NULL` → FREE (available)
- `clientId = 123` → OCCUPIED (client 123's items)

### Schema

```sql
CREATE TABLE client (
    id INT PRIMARY KEY,
    name VARCHAR(255)
);

CREATE TABLE part (
    id INT PRIMARY KEY,
    code VARCHAR(50),
    description TEXT,
    clientId INT,
    FOREIGN KEY (clientId) REFERENCES client(id)
);

CREATE TABLE location (
    id INT PRIMARY KEY,
    code VARCHAR(50) UNIQUE,
    clientId INT NULL,  -- NULL = FREE, value = OCCUPIED
    FOREIGN KEY (clientId) REFERENCES client(id)
);
```

---

## Verification

### Check Docker Containers

```bash
docker ps
```

Expected:
```
CONTAINER ID   IMAGE              PORTS                    NAMES
abc123         mysql:8.0          0.0.0.0:3307->3306/tcp   warehouse-mysql
def456         ollama/ollama      0.0.0.0:11434->11434/tcp warehouse-ollama
```

### Verify MySQL Data

```bash
docker exec warehouse-mysql mysql -uroot -pwarehouse_root_2024 -e \
  "SELECT COUNT(*) FROM location" mydatabase_gdpr
```

Expected: `31416`

### Verify Ollama Model

```bash
docker exec warehouse-ollama ollama list
```

Expected: `llama3.2:latest`

### Test System

```bash
python warehouse_cli.py 600
```

Expected: Recommendation for Part 600 with location TP49A

---

## Common Issues

### Port Already in Use

Error: `Port 3307 is already in use`

Solution - Change port in `docker-compose.yml`:
```yaml
mysql:
  ports:
    - "3308:3306"
```

Update `.env`:
```env
MYSQL_PORT=3308
```

### Qdrant Connection Failed

Error: `Failed to connect to Qdrant`

Solution:
1. Verify URL and API key in `.env`
2. Check internet connection
3. Ensure collection `PartSummary` exists

### Ollama Model Not Found

Error: `Model 'llama3.2' not found`

Solution:
```bash
docker exec warehouse-ollama ollama pull llama3.2
docker exec warehouse-ollama ollama list
```

### MySQL Connection Timeout

Error: `Failed to connect to MySQL`

Solution:
```bash
docker ps | grep warehouse-mysql
docker logs warehouse-mysql
docker-compose restart mysql
# Wait 30 seconds for initialization
```

### Empty Database

Error: Part not found

Solution:
```bash
# Check if data imported
docker exec warehouse-mysql mysql -uroot -pwarehouse_root_2024 -e \
  "SELECT COUNT(*) FROM part" mydatabase_gdpr

# If zero, reimport
docker-compose down mysql
docker volume rm local-deployment_mysql_data
docker-compose up -d mysql
```

---

## Usage Examples

### CLI Basic Query

```bash
python warehouse_cli.py 600
```

Output:
```
RECOMMENDED LOCATION: TP49A
  Status:           FREE
  Historical Usage: 2x out of 53 putaways

  ALTERNATIVES:
    1. TN43D - FREE
    2. TN49B - FREE

  AI SUMMARY: I recommend storing Part '42645EQ' in Location TP49A,
  as it aligns with our historical data and is currently available.
```

### CLI Interactive Mode

```bash
python warehouse_cli.py

Enter Part ID: 600
# Shows recommendation

Check another part? (Y/n): y
Enter Part ID: 1250
# Shows recommendation for part 1250

Check another part? (Y/n): n
```

### Web Interface

```bash
streamlit run app.py
```

1. Open http://localhost:8501
2. Enter Part ID: `600`
3. Click "Search"
4. View recommendation with alternatives
5. Confirm or override location

---

## Security Checklist

- [ ] Change default MySQL password in `.env`
- [ ] Do not commit `.env` to public repositories
- [ ] Use environment-specific Qdrant API keys
- [ ] Restrict Docker ports to localhost in production
- [ ] Regularly backup MySQL database
- [ ] Keep Docker images updated

---

## System Requirements

**Minimum:**
- 4GB RAM
- 10GB free disk space
- Internet connection (for Qdrant API)
- Docker Desktop
- Python 3.8+

**Recommended:**
- 8GB RAM
- 20GB free disk space
- Docker Desktop with WSL2 (Windows)
- Python 3.10+

---

## Quick Reference

### Start System
```bash
docker-compose up -d
streamlit run app.py
```

### Stop System
```bash
docker-compose down
```

### View Logs
```bash
docker-compose logs -f
```

### Backup Database
```bash
docker exec warehouse-mysql mysqldump -uroot -pwarehouse_root_2024 \
  mydatabase_gdpr > backup.sql
```

### Update Model
```bash
docker exec warehouse-ollama ollama pull llama3.2
```

---

## Debug Commands

```bash
# Container logs
docker-compose logs
docker logs warehouse-mysql
docker logs warehouse-ollama

# Container status
docker ps -a

# Test connections
docker exec warehouse-mysql mysql -uroot -pwarehouse_root_2024 -e "SELECT 1"
curl http://localhost:11434/api/tags
```
