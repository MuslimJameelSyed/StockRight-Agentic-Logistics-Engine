# Knowledge Base - What Data is Stored vs. Real-Time

## Quick Answer

**YES - Patterns contain historical data and snapshot inventory**
**NO - Patterns do NOT contain real-time availability (FREE/OCCUPIED status)**

---

## What IS Stored in Knowledge Base (Offline/Static)

### 1. **Historical Putaway Patterns** ✓

**Full details stored:**
```json
"locations": [
  {
    "code": "TP03D",
    "zone": "T",
    "aisle": "P",
    "column": "03",
    "row": "D",
    "count": 3,                           // Used 3 times historically
    "percentage": 5.66,                   // 5.66% of all putaways
    "first_used_date": "2023-09-08",      // First time used
    "last_used_date": "2023-09-22",       // Last time used
    "consecutive_uses": 3                 // Used 3 times in a row
  }
]
```

**Example - Part 600:**
- Stored 53 historical putaways
- 36 different locations used over time
- Each location with frequency, dates, percentages
- Zone/aisle/column/row breakdown
- Pattern strength analysis

---

### 2. **Current Inventory Snapshot** ✓

**Captured at knowledge base creation (2026-01-29):**
```json
"current_inventory": {
  "total_locations": 3,
  "total_onhand": 1680000.0,
  "total_reserved": 0.0,
  "total_available": 1680000.0,
  "locations": [
    {
      "location_code": "TN52D",
      "onHand": 600000.0,
      "reserved": 0.0,
      "onHold": 0.0,
      "available": 600000.0,
      "lot": "1003441084",
      "clientId": 34                      // Snapshot: Was 34 on 2026-01-29
    }
  ]
}
```

**Important:** This is a SNAPSHOT from when knowledge base was created.
- Shows what inventory existed on 2026-01-29
- Shows which client occupied location then
- **NOT updated in real-time**

---

### 3. **Statistical Analysis** ✓

**Stored pattern intelligence:**
```json
{
  "total_putaways": 53,
  "zone_distribution": {
    "T": 96.23,
    "S": 3.77
  },
  "aisle_distribution": {
    "P": 47.17,
    "N": 47.17
  },
  "pattern_strength": "WEAK",
  "pattern_stability": "SHIFTING",
  "consistency_ratio": 0.06,
  "confidence_score": 0.43,
  "recency_status": "DORMANT",
  "days_since_last_use": 188
}
```

---

### 4. **Client Preferences** ✓

**Stored in client summaries:**
```json
{
  "client_id": 34,
  "client_name": "Client 34",
  "total_parts": 150,
  "primary_zones": ["T", "S", "R"],
  "primary_aisles": ["P", "N"],
  "zone_distribution": {
    "T": 85%,
    "S": 10%,
    "R": 5%
  }
}
```

---

## What is NOT Stored (Real-Time Queries)

### 1. **Location Availability Status** ✗

**NOT in knowledge base - Queried real-time:**
```python
# This is queried from MySQL in REAL-TIME
query = """
    SELECT clientId
    FROM location
    WHERE code = %s
"""

# Results:
# clientId = NULL          → Location is FREE
# clientId = your_client   → Location is YOUR_LOCATION
# clientId = other_client  → Location is OCCUPIED
```

**Why not stored?**
- Changes constantly (inventory moves daily)
- Would be outdated immediately
- Must be current to avoid conflicts

---

### 2. **Current Inventory Quantities** ✗

**NOT in knowledge base - Queried real-time:**
```python
# This is queried from MySQL in REAL-TIME
query = """
    SELECT
        location.code,
        SUM(inventory.quantity) as current_qty,
        location.clientId
    FROM inventory
    JOIN location ON inventory.locationId = location.id
    WHERE inventory.partId = %s
      AND inventory.quantity > 0
    GROUP BY location.code
"""
```

**Why not stored?**
- Inventory changes hourly/daily
- Need accurate current quantities
- Affects consolidation decisions

---

### 3. **Location Capacity/Space** ✗

**NOT in knowledge base - Would need real-time query:**
```python
# Not currently implemented, but would need real-time:
query = """
    SELECT
        code,
        max_capacity,
        current_usage,
        available_space
    FROM location
    WHERE code = %s
"""
```

---

### 4. **Other Clients' Current Activity** ✗

**NOT in knowledge base - Real-time data:**
- Which locations other clients are using NOW
- Recent putaways by other clients
- Current space utilization

---

## How the System Works: Hybrid Approach

### Knowledge Base (Offline) + Database (Real-Time)

```
┌─────────────────────────────────────────────────────────┐
│              RECOMMENDATION PROCESS                      │
└─────────────────────────────────────────────────────────┘

Step 1: Load from Knowledge Base (Fast, Offline)
├─ Part ID: 600
├─ Historical patterns: 53 putaways
├─ Snapshot inventory: 3 locations (from 2026-01-29)
├─ Top historical locations: TP03D, TN40D, TP42E
└─ Client preferences: Zone T (96%), Aisle P/N

Step 2: Query Database Real-Time (Current, Live)
├─ Current inventory NOW:
│  SELECT location, quantity FROM inventory WHERE partId=600
│  Result: TN52D (600k), TP55C (600k), TN30D (480k)
│
├─ Check availability NOW:
│  SELECT clientId FROM location WHERE code='TN52D'
│  Result: clientId=34 (YOUR_LOCATION if you're Client 34)
│
└─ Validate each recommendation:
   For each location in [TN52D, TP55C, TN30D]:
     - Is it FREE? (clientId IS NULL)
     - Is it YOUR_LOCATION? (clientId = your_client)
     - Is it OCCUPIED? (clientId = other_client)

Step 3: Combine & Recommend
├─ Primary: Use current inventory (consolidation)
├─ Validate: Check availability real-time
├─ Fallback: Use historical patterns if needed
└─ Final: Return top 3-5 valid recommendations
```

---

## Example: Part 600 Recommendation Process

### From Knowledge Base (Loaded Once):
```json
{
  "part_id": 600,
  "historical_patterns": {
    "top_locations": ["TP03D", "TN40D", "TP42E"]
  },
  "current_inventory_snapshot": {
    "total_onhand": 1680000.0,  // Snapshot from 2026-01-29
    "locations": ["TN52D", "TP55C", "TN30D"]
  }
}
```

### From Database (Queried Real-Time):
```python
# Query 1: Get CURRENT inventory (not snapshot)
result = query("SELECT location, quantity FROM inventory WHERE partId=600")
# Returns: TN52D (current qty), TP55C (current qty), TN30D (current qty)

# Query 2: Check availability for TN52D
result = query("SELECT clientId FROM location WHERE code='TN52D'")
# Returns: clientId=34

# Query 3: Check if clientId=34 is YOUR client
if current_user_client == 34:
    status = "YOUR_LOCATION"  # You already use this
elif clientId is None:
    status = "FREE"  # Available
else:
    status = "OCCUPIED"  # Someone else uses it
```

### Final Recommendation:
```
Part 600 Recommendations:
1. TN52D - YOUR_LOCATION - 600,000 units exist ✓
2. TP55C - YOUR_LOCATION - 600,000 units exist ✓
3. TN30D - YOUR_LOCATION - 480,000 units exist ✓

Strategy: CONSOLIDATION
Confidence: 99%
```

---

## Why This Hybrid Approach?

### Advantages:

**1. Speed**
- Knowledge base loads once (98 MB)
- No repeated queries for historical data
- Only query database for current state

**2. Accuracy**
- Availability always current
- No stale FREE/OCCUPIED data
- Real-time conflict prevention

**3. Intelligence**
- Learn from historical patterns (stored)
- Validate against current reality (queried)
- Best of both worlds

**4. Efficiency**
- 98 MB knowledge base vs constant DB queries
- Pattern analysis pre-computed
- Only essential real-time queries

---

## Data Freshness

### Knowledge Base (Updated Periodically)

**Last Updated:** 2026-01-29

**Contains:**
- Historical patterns (up to 2026-01-29)
- Inventory snapshot (as of 2026-01-29)
- Client preferences (aggregated historical)

**Update frequency:**
- Manual: `python add_inventory_patterns.py`
- Recommended: Weekly or monthly
- Or: When significant pattern changes occur

---

### Database (Always Current)

**Always Live:**
- Current inventory quantities
- Location availability (FREE/OCCUPIED/YOUR_LOCATION)
- Recent transactions
- Client assignments

**Update frequency:** Real-time (every query)

---

## What Happens if Knowledge Base is Outdated?

### Scenario: Knowledge base from 2026-01-29, Today is 2026-06-30

**Knowledge Base Says:**
```json
"current_inventory": {
  "locations": ["TN52D", "TP55C", "TN30D"],
  "total_onhand": 1680000.0
}
```

**Database Says (Real-Time):**
```sql
SELECT * FROM inventory WHERE partId=600
-- Result: RM05A (1,050 units), RM04A (900 units)
-- (Inventory moved from TN* to RM* locations)
```

**System Behavior:**
1. ✓ Queries database for CURRENT inventory
2. ✓ Gets real locations: RM05A, RM04A
3. ✓ Recommends based on CURRENT data: RM05A, RM04A
4. ✗ Knowledge base snapshot ignored (outdated)

**Result:** System still works correctly! Real-time data takes precedence.

---

### Scenario: Historical patterns outdated

**Knowledge Base Says:**
```json
"historical_patterns": {
  "top_locations": ["TP03D (3 times)", "TN40D (2 times)"]
}
```

**Reality:**
- Part 600 now consistently goes to RM05A (50 new putaways since 2026-01-29)
- Pattern changed significantly

**System Behavior:**
1. If current inventory exists: Uses real-time inventory (correct)
2. If no inventory: Uses outdated historical patterns (suboptimal)

**Impact:** Medium
- System works but may suggest older locations
- Not critical (supervisor can override)
- Fix: Update knowledge base monthly

---

## Summary Table

| Data Type | Stored in KB? | Queried Real-Time? | Staleness Risk | Update Frequency |
|-----------|---------------|-------------------|----------------|------------------|
| **Historical putaway patterns** | ✓ YES | ✗ No | Medium | Weekly/Monthly |
| **Inventory snapshot** | ✓ YES | ✗ No | High | Daily/Weekly |
| **Client preferences** | ✓ YES | ✗ No | Low | Monthly |
| **Zone/aisle distributions** | ✓ YES | ✗ No | Low | Monthly |
| **Pattern strength analysis** | ✓ YES | ✗ No | Medium | Monthly |
| | | | | |
| **Current inventory quantities** | ✗ No | ✓ YES | None | Real-time |
| **Location availability (FREE/OCCUPIED)** | ✗ No | ✓ YES | None | Real-time |
| **Location.clientId** | ✗ No | ✓ YES | None | Real-time |
| **Recent transactions** | ✗ No | ✓ YES | None | Real-time |
| **Current space utilization** | ✗ No | ✓ YES | None | Real-time |

---

## Key Takeaways

### ✓ Knowledge Base Contains:
1. **Historical putaway patterns** (all dates, frequencies, percentages)
2. **Inventory snapshot** (from 2026-01-29)
3. **Statistical analysis** (pattern strength, distributions)
4. **Client preferences** (zone/aisle tendencies)
5. **Pre-computed intelligence** (confidence scores, recommendations)

### ✗ Knowledge Base Does NOT Contain:
1. **Real-time availability** (FREE/OCCUPIED - must query)
2. **Current inventory** (uses real-time query instead of snapshot)
3. **Live location status** (who occupies what NOW)
4. **Dynamic space availability** (current capacity)
5. **Other clients' current activity**

### 🔄 Hybrid Approach:
- **Fast**: Load knowledge base once (patterns, preferences)
- **Accurate**: Query database for current state (inventory, availability)
- **Intelligent**: Combine historical wisdom with current reality
- **Reliable**: Always uses latest data for critical decisions

---

## Recommendation: Update Schedule

### Daily (Automated):
```bash
# Update inventory snapshot in knowledge base
python add_inventory_patterns.py
python upload_to_qdrant.py
```

### Weekly (Manual):
- Review pattern changes
- Check for new high-volume parts
- Verify confidence scores

### Monthly (Comprehensive):
- Full knowledge base regeneration
- Pattern analysis review
- Client preference updates
- System performance audit

---

**Version:** 1.0
**Date:** 2026-01-30
**Knowledge Base Last Updated:** 2026-01-29
**Explanation:** Complete
