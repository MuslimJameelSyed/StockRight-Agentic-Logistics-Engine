# Warehouse Putaway System - User Guide

**For Warehouse Operators**

---

## Table of Contents
1. [Getting Started](#getting-started)
2. [How to Get Recommendations](#how-to-get-recommendations)
3. [Understanding Results](#understanding-results)
4. [Override Recommendations](#override-recommendations)
5. [Troubleshooting](#troubleshooting)

---

## Getting Started

### What is This System?

The Warehouse Putaway System tells you **where to store incoming parts** based on:
- **Historical data** - Where this part was stored before
- **Real-time availability** - Which locations are FREE right now
- **AI recommendations** - Clear explanations in plain language

### How to Access

**Web Interface:**
- Open your web browser
- Go to the system URL (ask your supervisor)
- You'll see a search box

---

## How to Get Recommendations

### Step 1: Enter Part ID

1. Look at the part label or paperwork
2. Find the **Part ID** (example: 600, 1234, etc.)
3. Type it in the search box
4. Click the blue **🔎 Search** button

![Search Example](search_example.png)

### Step 2: View Recommendation

The system will show you:

**📦 Part Information**
- Part ID: #600
- Part Code: 42645EQ
- Client: Client 34
- Description: TIPS

**⭐ Recommended Location**
- **Location Code:** TP49A ← This is where you should put the part
- **Status:** ✓ FREE (available now)
- **Historical Usage:** 2x / 53 (used 2 times before)
- **Usage Rate:** 3.8%

---

## Understanding Results

### What Does Each Field Mean?

| Field | Meaning | Example |
|-------|---------|---------|
| **Location Code** | The shelf/bin location | TP49A, TN52D, SG01J |
| **Status** | Is it available? | ✓ FREE or OCCUPIED |
| **Historical Usage** | How many times used before | 2x / 53 (2 times out of 53 total) |
| **Usage Rate** | Percentage of times used | 3.8% |

### Pattern Strength

The system shows how reliable the recommendation is:

- **STRONG** (🟢) - Used 20%+ of the time, or 3+ times in a row
  - *Very reliable, follow this recommendation*

- **MODERATE** (🟡) - Used 10-20% of the time, or 2 times in a row
  - *Good recommendation, but alternatives exist*

- **WEAK** (🟠) - Used less than 10% of the time
  - *Less reliable, consider alternatives*

### AI Explanation

The system provides a simple explanation:

> "Store part 42645EQ in location TP49A. This part was historically put in TP49A 2 times, so this is the best location to put it now. The location is currently free."

**This tells you:**
- Where to put it (TP49A)
- Why (historically used)
- That it's available (free)

---

## Override Recommendations

### When to Override

You might choose a different location if:
- The recommended location is hard to reach
- You have a better location nearby
- Supervisor instructs you differently
- The location doesn't make sense

### How to Override

1. Scroll to the **🔄 Override Recommendation** section
2. Click the dropdown menu
3. Choose a different location from the list
   - All locations shown are verified as FREE
   - Usage stats are shown for each option
4. Click **✓ Confirm Selection** button

**Example:**
```
— Use Recommended Location —
TP49A (used 2x, 3.8%)   ← Recommended
TN43D (used 1x, 1.9%)   ← Alternative
TN49B (used 1x, 1.9%)   ← Alternative
```

### What Happens When You Override?

- ✅ Your choice is recorded in the system logs
- ✅ Supervisors can review override decisions
- ✅ System learns from your choices over time

---

## Troubleshooting

### Problem: "Part ID must be a number"

**Cause:** You entered text instead of a number

**Solution:**
- Only enter numbers (e.g., 600, 1234)
- Don't include letters or symbols

### Problem: "Part 12345 not found in database"

**Cause:** The part ID doesn't exist

**Solution:**
- Double-check the part ID
- Verify the number on the part label
- Ask your supervisor if the part is new

### Problem: "No historical putaway data found"

**Meaning:** This part has never been stored before

**What to do:**
- Contact your supervisor
- They will assign a location
- The system will learn for next time

### Problem: "All historically used locations are currently occupied"

**Meaning:** All the usual locations are full

**What to do:**
- The system suggests a warehouse zone
- Ask your supervisor for guidance
- Use a similar location in that zone

### Problem: "Unable to connect to database"

**Meaning:** System can't reach the database

**What to do:**
- Wait a moment and try again (system retries automatically)
- If it persists, contact your supervisor
- Check your internet connection

---

## Best Practices

### ✅ DO:
- Follow the recommended location when possible
- Override only when necessary
- Confirm your selection before proceeding
- Report any system issues to your supervisor

### ❌ DON'T:
- Ignore recommendations without good reason
- Store parts in unverified locations
- Use FLOOR*, REC*, or ORD* locations (temporary only)
- Forget to confirm your final choice

---

## Quick Reference Card

**📋 Quick Steps:**

1. **Enter Part ID** → Type number, click Search
2. **Read Recommendation** → Note the location code
3. **Check Status** → Verify it shows ✓ FREE
4. **Use Location** → Store part in recommended spot
5. **Override if Needed** → Choose alternative, click Confirm

**🆘 Need Help?**
- Part not found → Check supervisor
- All locations occupied → Ask supervisor for zone
- System error → Wait and retry, then report if persistent

**✓ System Status Colors:**
- 🟢 GREEN (FREE) - Location available, use it
- 🔴 RED (OCCUPIED) - Location in use, don't use

---

## Frequently Asked Questions

**Q: What if I disagree with the recommendation?**
A: You can override it. Choose an alternative from the dropdown. All alternatives shown are FREE.

**Q: Can I use a location not on the list?**
A: No. Only use locations shown by the system. They are verified as FREE in real-time.

**Q: What does "Historical Usage 15x / 53" mean?**
A: This part was stored in this location 15 times out of 53 total times it was put away.

**Q: Why does it say OCCUPIED sometimes?**
A: The location is currently being used by another part. Don't use it.

**Q: Is the system always right?**
A: The system is 100% accurate at finding historical patterns and checking availability. But you can override if needed.

**Q: What happens to my override decisions?**
A: They are logged for analysis. Over time, the system learns from operator choices.

---

**Need more help? Contact your warehouse supervisor.**

**System Version:** 1.0.0 (Production-Ready)
