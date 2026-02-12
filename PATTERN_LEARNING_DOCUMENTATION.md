# StockRight Pattern Learning System
## How the System Learns from Historical Data

---

## Overview

The **StockRight Agentic Logistics Engine** learns warehouse storage patterns by analyzing past transactions. Think of it like teaching a student by showing examples - the system "learns" by looking at where parts were stored historically.

---

## 1. What is Pattern Learning?

**Simple Definition:**
Pattern learning means finding repeated behaviors in historical data.

**In Our System:**
- We have **224,081 past putaway transactions** (records of where parts were stored)
- System analyzes these transactions to find patterns like:
  - "Part A is usually stored in Location X"
  - "Part B is mostly placed in Zone T"

**Example:**
If Part 600 was stored 53 times in the past:
- 15 times in location TN52D (28.3%)
- 8 times in location SG01J (15.1%)
- 3 times in location TP03D (5.66%)

The system learns: **"Part 600 prefers TN52D location"**

---

## 2. Data Sources

### Input Data (MySQL Database)

**Transaction Table:**
```
224,081 total transactions
From: 87 different clients
For: 3,215 unique parts
Across: 31,416 warehouse locations
```

**Each Transaction Contains:**
- Part ID (which part was stored)
- Location ID (where it was placed)
- Client ID (who owns the part)
- Timestamp (when it was stored)

**Example Transaction:**
```
Transaction #12345
├─ Part: 600 (Code: 42645EQ - Bearing)
├─ Location: TN52D
├─ Client: ABC Corporation
└─ Date: 2024-08-15
```

---

## 3. Pattern Extraction Process (Aggregation Pipeline)

### Step-by-Step Learning

**STEP 1: Filter Invalid Locations**
```
Remove locations that are not real storage spots:
❌ FLOOR1, FLOOR2 (temporary floor storage)
❌ REC001, REC002 (receiving areas)
❌ ORD001, ORD002 (order staging areas)
❌ Subdivided locations (TN52DD - duplicate letters)

✓ Keep only valid shelf locations (TN52D, SG01J, etc.)
```

**STEP 2: Group by Part**
```
Organize all transactions by Part ID
Part 600 → [53 transactions]
Part 842 → [120 transactions]
Part 1523 → [8 transactions]
...and so on for 3,215 parts
```

**STEP 3: Count Location Usage**
```
For each part, count how many times each location was used

Part 600 (53 total putaways):
  TN52D → 15 times
  SG01J → 8 times
  TP03D → 3 times
  TN43D → 1 time
  ...and more locations
```

**STEP 4: Calculate Percentages**
```
Convert counts to percentages for easy comparison

Part 600:
  TN52D → 15/53 = 28.3%
  SG01J → 8/53 = 15.1%
  TP03D → 3/53 = 5.66%
```

**STEP 5: Rank by Frequency**
```
Sort locations from most used to least used

Part 600 Rankings:
  #1: TN52D (28.3%) ← Most preferred location
  #2: SG01J (15.1%)
  #3: TP03D (5.66%)
  #4: TN43D (1.9%)
```

**STEP 6: Extract Primary Zone**
```
Identify the most common warehouse zone

Part 600:
  Most locations start with "T" (TN52D, TP03D, TN43D)
  → Primary Zone = "T"
```

---

## 4. MySQL Aggregation Query

**The SQL code that does the learning:**

```sql
SELECT
    p.id AS part_id,
    p.code AS part_code,
    l.code AS location_code,
    COUNT(*) AS usage_count,
    ROUND(COUNT(*) * 100.0 / total_putaways, 2) AS usage_percentage
FROM
    putaway_transaction pt
    JOIN part p ON pt.partId = p.id
    JOIN location l ON pt.locationId = l.id
    JOIN (
        -- Calculate total putaways for each part
        SELECT partId, COUNT(*) AS total_putaways
        FROM putaway_transaction
        GROUP BY partId
    ) totals ON p.id = totals.partId
WHERE
    -- Filter out invalid locations
    l.code NOT LIKE 'FLOOR%'
    AND l.code NOT LIKE 'REC%'
    AND l.code NOT LIKE 'ORD%'
    AND l.code NOT REGEXP '[A-Z]{2}[0-9]{2}[A-Z]{2}$'  -- No subdivisions
GROUP BY
    p.id, l.code
ORDER BY
    p.id, usage_count DESC
```

**What This Query Does:**
1. Joins transaction data with part and location information
2. Filters out invalid storage locations
3. Groups transactions by part and location
4. Counts how many times each part was stored in each location
5. Calculates the percentage of usage for each location
6. Sorts results by most-used locations first

---

## 5. Learned Pattern Structure

### Pattern Format (JSON)

**For Each Part:**
```json
{
    "part_id": 600,
    "part_code": "42645EQ",
    "description": "Bearing",
    "client_id": 15,
    "client_name": "ABC Corporation",
    "total_putaways": 53,
    "primary_zone": "T",
    "all_locations": [
        {
            "code": "TN52D",
            "count": 15,
            "percentage": 28.3
        },
        {
            "code": "SG01J",
            "count": 8,
            "percentage": 15.1
        },
        {
            "code": "TP03D",
            "count": 3,
            "percentage": 5.66
        }
    ]
}
```

**What Each Field Means:**
- `part_id`: Unique identifier for the part
- `part_code`: Human-readable part code
- `total_putaways`: How many times this part was stored historically
- `primary_zone`: Most common warehouse zone (first letter of locations)
- `all_locations`: List of all locations used, ranked by frequency
  - `code`: Location name
  - `count`: Number of times used
  - `percentage`: Usage rate (count ÷ total_putaways × 100)

---

## 6. Knowledge Base Creation

### Storing Patterns in Qdrant Vector Database

**Why Qdrant?**
- Fast retrieval (milliseconds to find patterns for any part)
- Scalable (can handle millions of parts)
- Cloud-based (accessible from anywhere)

**Storage Process:**

```
MySQL Aggregation Results
    ↓
Process 224,081 transactions
    ↓
Extract patterns for 3,215 parts
    ↓
Create 2,492 learned patterns
    ↓
Store in Qdrant "PartSummary" collection
```

**Why Only 2,492 Patterns from 3,215 Parts?**
- Some parts have no valid historical locations (only stored in FLOOR/REC areas)
- Some parts were stored only once (not enough data to learn a pattern)
- We only create patterns for parts with 2+ valid putaways

**Qdrant Collection Details:**
```
Collection Name: PartSummary
Total Vectors: 2,492 patterns
Vector Dimension: Not applicable (using payload storage only)
Index Type: Integer ID-based lookup
```

**How Data is Stored:**
```python
# Each pattern is stored with Part ID as the unique identifier
qdrant.upsert(
    collection_name="PartSummary",
    points=[
        {
            "id": 600,  # Part ID (used for fast lookup)
            "payload": {
                "part_code": "42645EQ",
                "total_putaways": 53,
                "primary_zone": "T",
                "all_locations": [...]
            }
        }
    ]
)
```

---

## 7. Learning Statistics

### Overall Pattern Learning Results

**Input Data:**
```
Total Transactions Analyzed: 224,081
Unique Parts in Database: 3,215
Unique Locations: 31,416
Unique Clients: 87
```

**Output Data:**
```
Learned Patterns Created: 2,492
Coverage: 77.5% of all parts
Average Putaways per Part: 90 transactions
Parts with Strong Patterns (>10 putaways): 1,847
Parts with Weak Patterns (2-10 putaways): 645
```

**Pattern Quality Distribution:**
```
High Confidence (>50% usage on top location): 892 parts (35.8%)
Medium Confidence (20-50% usage): 1,156 parts (46.4%)
Low Confidence (<20% usage): 444 parts (17.8%)
```

**Example High-Confidence Pattern:**
```
Part 1234 (High Confidence)
├─ Total putaways: 150
├─ Top location: TP49A (78 times = 52%)
└─ Pattern strength: STRONG ✓
```

**Example Low-Confidence Pattern:**
```
Part 5678 (Low Confidence)
├─ Total putaways: 12
├─ Top location: SG01J (3 times = 25%)
└─ Pattern strength: WEAK (spread across many locations)
```

---

## 8. How Patterns Are Used for Recommendations

### Recommendation Flow

**When a part arrives at the warehouse:**

```
1. User enters Part ID (e.g., 600)
   ↓
2. System retrieves learned pattern from Qdrant
   ↓
3. System gets top historical locations:
   - TN52D (28.3%)
   - SG01J (15.1%)
   - TP03D (5.66%)
   ↓
4. System checks which locations are FREE in MySQL
   ↓
5. System recommends the most-used FREE location
   ↓
6. If TN52D is FREE → Recommend it ✓
   If TN52D is OCCUPIED → Recommend SG01J (next best)
```

**AI Explanation Generation:**
```
Gemini AI receives:
- Part: 42645EQ (Bearing)
- Recommended Location: TN52D
- Confidence: 28.3% historical usage
- Status: FREE

AI generates:
"Location TN52D is recommended as it has been the most frequently
used location for this part historically. The location is currently
FREE and ready for immediate use."
```

---

## 9. Benefits of Pattern Learning

**Why This Approach Works:**

### 1. Data-Driven Decisions
- Recommendations based on 224,081 real transactions
- Not guessing - using proven historical patterns
- Reduces human error in location selection

### 2. Efficiency
- Fast lookups (< 100ms from Qdrant)
- No need to manually remember where parts go
- Consistent storage strategy across warehouse

### 3. Adaptability
- Patterns can be updated with new transactions
- System learns from changing warehouse practices
- Improves over time as more data is collected

### 4. Transparency
- Shows users WHY a location is recommended
- Provides confidence scores (usage percentages)
- Allows manual override if needed

---

## 10. System Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│           HISTORICAL TRANSACTION DATA                   │
│                (MySQL Database)                          │
│                                                           │
│  224,081 putaway transactions                            │
│  3,215 unique parts                                      │
│  31,416 warehouse locations                              │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│         AGGREGATION PIPELINE (Learning Phase)            │
│                                                           │
│  Step 1: Filter invalid locations                        │
│  Step 2: Group by Part ID                                │
│  Step 3: Count location usage                            │
│  Step 4: Calculate percentages                           │
│  Step 5: Rank by frequency                               │
│  Step 6: Extract primary zone                            │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│         LEARNED PATTERNS (Qdrant Vector DB)              │
│                                                           │
│  Collection: PartSummary                                 │
│  Total Patterns: 2,492                                   │
│  Coverage: 77.5% of parts                                │
│                                                           │
│  Each pattern contains:                                  │
│  - Part identification                                   │
│  - Historical location rankings                          │
│  - Usage frequencies & percentages                       │
│  - Primary warehouse zone                                │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│         RECOMMENDATION ENGINE (Runtime)                  │
│                                                           │
│  Input: Part ID from user                                │
│    ↓                                                      │
│  Retrieve pattern from Qdrant                            │
│    ↓                                                      │
│  Check location availability (MySQL)                     │
│    ↓                                                      │
│  Rank available locations                                │
│    ↓                                                      │
│  Generate AI explanation (Gemini)                        │
│    ↓                                                      │
│  Output: Smart location recommendation                   │
└─────────────────────────────────────────────────────────┘
```

---

## 11. Example: Complete Pattern Learning Journey

### Scenario: Learning Pattern for Part 600 (Bearing - 42645EQ)

**Starting Point:**
```
Part 600 has been stored 53 times in warehouse history
```

**Step 1: Collect Raw Transactions**
```
Transaction Log:
2024-01-10: Part 600 → TN52D (Client: ABC Corp)
2024-01-15: Part 600 → SG01J (Client: ABC Corp)
2024-01-20: Part 600 → TN52D (Client: ABC Corp)
2024-02-05: Part 600 → TN52D (Client: ABC Corp)
2024-02-12: Part 600 → TP03D (Client: ABC Corp)
... (48 more transactions)
```

**Step 2: Aggregate Data**
```sql
Results from aggregation query:

Location  | Count | Percentage
----------|-------|------------
TN52D     | 15    | 28.3%
SG01J     | 8     | 15.1%
TP03D     | 3     | 5.66%
TN43D     | 1     | 1.9%
... (more locations with small percentages)
```

**Step 3: Create Pattern Structure**
```json
{
    "part_id": 600,
    "part_code": "42645EQ",
    "description": "Bearing",
    "total_putaways": 53,
    "primary_zone": "T",
    "all_locations": [
        {"code": "TN52D", "count": 15, "percentage": 28.3},
        {"code": "SG01J", "count": 8, "percentage": 15.1},
        {"code": "TP03D", "count": 3, "percentage": 5.66},
        {"code": "TN43D", "count": 1, "percentage": 1.9}
    ]
}
```

**Step 4: Store in Qdrant**
```
Pattern saved to PartSummary collection
ID: 600
Status: Ready for recommendations ✓
```

**Step 5: Use Pattern for Recommendation**
```
User Query: "Where should I put Part 600?"

System Response:
┌─────────────────────────────────────┐
│  RECOMMENDED LOCATION: TN52D        │
│  Status: FREE ✓                     │
│  Historical Usage: 15× / 53 (28.3%) │
│                                     │
│  AI Summary:                        │
│  Location TN52D is recommended as   │
│  it follows the established pattern │
│  for this part. The location is     │
│  currently FREE and ready for use.  │
│                                     │
│  ALTERNATIVES:                      │
│  #1: SG01J (15.1%) - FREE           │
│  #2: TP03D (5.66%) - FREE           │
└─────────────────────────────────────┘
```

---

## Conclusion

The **StockRight Pattern Learning System** transforms historical warehouse data into actionable recommendations:

1. **Learns** from 224,081 real transactions
2. **Extracts** patterns using SQL aggregation
3. **Stores** 2,492 patterns in Qdrant for fast access
4. **Recommends** optimal locations based on proven historical usage
5. **Explains** recommendations using AI-powered natural language

This data-driven approach ensures efficient warehouse operations while maintaining flexibility for manual overrides when needed.

---

**Document Version:** 1.0
**Last Updated:** February 2026
**System:** StockRight Agentic Logistics Engine (SALE)
