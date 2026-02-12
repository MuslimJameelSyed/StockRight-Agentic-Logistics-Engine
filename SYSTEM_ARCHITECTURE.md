# StockRight Agentic Logistics Engine - System Architecture

## High-Level System Flow

```


```

---

## System Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          PRESENTATION LAYER                               │
│                                                                            │
│  ┌──────────────────────┐              ┌──────────────────────┐          │
│  │  Streamlit Web UI    │              │   CLI Interface      │          │
│  │  (app.py)            │              │  (warehouse_cli.py)  │          │
│  │  - Dark theme UI     │              │  - Terminal commands │          │
│  │  - Input validation  │              │  - Batch processing  │          │
│  │  - Result display    │              │  - Script automation │          │
│  └──────────┬───────────┘              └──────────┬───────────┘          │
│             │                                     │                       │
└─────────────┼─────────────────────────────────────┼───────────────────────┘
              │                                     │
              └──────────────┬──────────────────────┘
                             │
┌─────────────────────────────▼─────────────────────────────────────────────┐
│                         APPLICATION LAYER                                  │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                  Recommendation Engine                               │  │
│  │  (get_recommendation function)                                       │  │
│  │                                                                       │  │
│  │  1. Part Validation                                                  │  │
│  │  2. Historical Pattern Retrieval                                     │  │
│  │  3. Location Availability Check                                      │  │
│  │  4. Location Filtering & Validation                                  │  │
│  │  5. Ranking Algorithm                                                │  │
│  │  6. AI Explanation Generation                                        │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐        │
│  │  Configuration   │  │  Error Handler   │  │  Audit Logger    │        │
│  │  (config.py)     │  │  (error_handler) │  │  (audit logs)    │        │
│  │  - Env vars      │  │  - Retry logic   │  │  - User actions  │        │
│  │  - Validation    │  │  - Error msgs    │  │  - Overrides     │        │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘        │
└─────────────────────────────────────────────────────────────────────────┘
              │                    │                      │
              ▼                    ▼                      ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           DATA LAYER                                     │
│                                                                           │
│  ┌───────────────────┐  ┌────────────────────┐  ┌──────────────────┐   │
│  │  Qdrant Cloud     │  │  MySQL Cloud SQL   │  │  Google Gemini   │   │
│  │  Vector Database  │  │  Relational DB     │  │  AI Model        │   │
│  ├───────────────────┤  ├────────────────────┤  ├──────────────────┤   │
│  │ Collection:       │  │ Tables:            │  │ Model:           │   │
│  │ • PartSummary     │  │ • part (3,215)     │  │ gemini-2.5-flash │   │
│  │                   │  │ • location (31,416)│  │                  │   │
│  │ Documents: 2,492  │  │ • client (87)      │  │ Purpose:         │   │
│  │                   │  │                    │  │ • Natural lang   │   │
│  │ Purpose:          │  │ Purpose:           │  │ • Explanations   │   │
│  │ • Historical      │  │ • Real-time data   │  │ • User-friendly  │   │
│  │   patterns        │  │ • Availability     │  │   responses      │   │
│  │ • Pattern counts  │  │ • Part details     │  │                  │   │
│  │ • Usage stats     │  │ • Client info      │  │                  │   │
│  └───────────────────┘  └────────────────────┘  └──────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow Sequence

```
Time →

User        Streamlit       Python          Qdrant         MySQL         Gemini       Streamlit
 │              │              │               │              │              │              │
 │──Part ID─→   │              │               │              │              │              │
 │   (600)      │              │               │              │              │              │
 │              │              │               │              │              │              │
 │              │──validate──→ │               │              │              │              │
 │              │              │               │              │              │              │
 │              │              │───get part──→ │              │              │              │
 │              │              │   info        │              │              │              │
 │              │              │ ←─part found──│              │              │              │
 │              │              │               │              │              │              │
 │              │              │──────get patterns──────────→ │              │              │
 │              │              │                              │              │              │
 │              │              │ ←─────historical data────────│              │              │
 │              │              │  (TP49A: 2×, TN43D: 1×)      │              │              │
 │              │              │                              │              │              │
 │              │              │───check availability for────→│              │              │
 │              │              │      TP49A, TN43D, SG01J     │              │              │
 │              │              │                              │              │              │
 │              │              │ ←────status (FREE/OCCUPIED)──│              │              │
 │              │              │      TP49A:FREE, TN43D:FREE  │              │              │
 │              │              │                              │              │              │
 │              │              │──rank & select best──→       │              │              │
 │              │              │   (TP49A wins)               │              │              │
 │              │              │                              │              │              │
 │              │              │────────generate AI summary──────────────────→│              │
 │              │              │                                              │              │
 │              │              │ ←──────AI explanation text───────────────────│              │
 │              │              │                                              │              │
 │              │ ←─recommendation result─│                                  │              │
 │              │                         │                                  │              │
 │              │───display UI──→         │                                  │              │
 │ ←─view result─│                        │                                  │              │
 │              │                         │                                  │              │
```

---

## Knowledge Base Construction (One-Time Setup)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    KNOWLEDGE BASE BUILD PROCESS                          │
│                    (Performed Once - Offline)                            │
└─────────────────────────────────────────────────────────────────────────┘

Step 1: Extract Historical Data
┌──────────────────────────────────┐
│  MySQL Database                  │
│  ┌────────────────────────────┐  │
│  │  putaway_transactions      │  │
│  │  (224,081 records)         │  │
│  │                            │  │
│  │  partId  | locationCode   │  │
│  │  --------|--------------- │  │
│  │   600    |   TP49A        │  │
│  │   600    |   TP49A        │  │
│  │   600    |   TN43D        │  │
│  │   ...    |   ...          │  │
│  └────────────────────────────┘  │
└──────────────┬───────────────────┘
               │
               ▼
Step 2: Aggregate Patterns (Python Script)
┌──────────────────────────────────┐
│  Pattern Aggregation Logic       │
│                                  │
│  For each Part ID:               │
│  • Count location frequency      │
│  • Calculate percentages         │
│  • Identify primary zone         │
│  • Compute confidence scores     │
│                                  │
│  Result: 2,492 part patterns     │
└──────────────┬───────────────────┘
               │
               ▼
Step 3: Upload to Qdrant
┌──────────────────────────────────┐
│  Qdrant Vector Database          │
│  Collection: PartSummary         │
│                                  │
│  Document Example (Part 600):    │
│  {                               │
│    "part_id": 600,               │
│    "total_putaways": 53,         │
│    "all_locations": [            │
│      {"code": "TP49A",           │
│       "count": 2,                │
│       "percentage": 3.8},        │
│      {"code": "TN43D",           │
│       "count": 1,                │
│       "percentage": 1.9}         │
│    ],                            │
│    "primary_zone": "T"           │
│  }                               │
└──────────────────────────────────┘
```

---

## Technology Stack

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend                                  │
│  • Streamlit (Python web framework)                             │
│  • Custom CSS (Dark theme, responsive design)                   │
│  • Pandas DataFrames (Table display)                            │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                        Backend                                   │
│  • Python 3.8+                                                  │
│  • mysql-connector-python (Database driver)                     │
│  • qdrant-client (Vector DB client)                             │
│  • google-generativeai (Gemini AI SDK)                          │
│  • python-dotenv (Environment management)                       │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                        Data Storage                              │
│  • Qdrant Cloud (Vector database - Historical patterns)         │
│  • Google Cloud SQL (MySQL - Real-time data)                    │
│  • Environment Variables (Credentials)                           │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                        AI/ML                                     │
│  • Google Gemini 2.5 Flash (LLM)                                │
│  • RAG Pattern (Retrieval-Augmented Generation)                 │
│  • Vector similarity (Qdrant internal)                           │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                        Deployment                                │
│  • Streamlit Cloud (Hosting)                                    │
│  • GitHub (Version control)                                      │
│  • Environment Secrets (Secure credentials)                      │
└─────────────────────────────────────────────────────────────────┘
```

---

## Key Design Decisions

### 1. **Why Qdrant for Historical Data?**
- ✓ Fast integer ID lookups
- ✓ Efficient storage for aggregated patterns
- ✓ Scalable (millions of documents)
- ✓ No complex queries needed

### 2. **Why MySQL for Real-Time Data?**
- ✓ ACID compliance (data consistency)
- ✓ Complex relational queries
- ✓ Transaction support
- ✓ Existing enterprise integration

### 3. **Why Separate Historical & Real-Time?**
- ✓ Historical patterns rarely change → Cache-friendly
- ✓ Real-time availability changes constantly → Fresh data
- ✓ Different query patterns → Optimized for each
- ✓ Fault isolation (Qdrant down ≠ MySQL down)

### 4. **Why Gemini AI?**
- ✓ Natural language explanations
- ✓ Context-aware responses
- ✓ User-friendly communication
- ✓ Low latency (flash model)

---

## Performance Characteristics

| Operation                  | Latency    | Cache | Scalability        |
|---------------------------|------------|-------|--------------------|
| Part Validation           | ~50ms      | No    | Linear (O(1))      |
| Historical Pattern Lookup | ~100ms     | Yes   | Constant (O(1))    |
| Availability Check        | ~30ms/loc  | No    | Linear (O(n locs)) |
| AI Generation             | ~500ms     | No    | Varies             |
| **Total Response Time**   | **~1-2s**  | Mixed | **Good**           |

---

Generated: 2026-02-12
System: StockRight Agentic Logistics Engine (SALE)
