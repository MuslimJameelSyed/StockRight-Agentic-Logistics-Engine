"""
INTERACTIVE WAREHOUSE ASSISTANT (LOCAL MODE)

Works WITHOUT Qdrant - uses local knowledge base files
Faster startup, no internet needed for recommendations

A conversational AI that answers warehouse questions:
- "Where should I put Part 600?"
- "Which locations are empty?"
- "What's in location G12G?"
- "Show me all parts for Client 34"
"""

import mysql.connector
import json
import os
import re

# Database connection
print("Connecting to database...")
db = mysql.connector.connect(
    host='localhost',
    port=3307,
    database='mydatabase_gdpr',
    user='root',
    password='rootpassword'
)
print("Ready!\n")

# Path to knowledge base
KB_PATH = "../knowledge_base/parts"

# Helper functions
def extract_part_id(text):
    """Extract part ID from text"""
    match = re.search(r'\b(?:part\s+)?(\d{1,5})\b', text, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None

def extract_location_code(text):
    """Extract location code from text"""
    match = re.search(r'\b([A-Z]{1,2}\d{2}[A-Z])\b', text, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return None

def extract_client_id(text):
    """Extract client ID from text"""
    match = re.search(r'\b(?:client\s+)?(\d{1,3})\b', text, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None

def is_valid_location(location_code):
    """Filter invalid locations"""
    if not location_code:
        return False
    if location_code.startswith('FLOOR') or \
       location_code.startswith('REC') or \
       location_code.startswith('ORD'):
        return False
    if len(location_code) >= 2:
        last_two = location_code[-2:]
        if last_two.isalpha() and last_two[0] == last_two[1]:
            return False
    return True

def load_part_data(part_id):
    """Load part data from local knowledge base"""
    kb_file = os.path.join(KB_PATH, f"part_{part_id}.json")

    if os.path.exists(kb_file):
        with open(kb_file, 'r') as f:
            return json.load(f)
    return None

def check_location_availability(location_code, requesting_client_id):
    """Check if location is available"""
    cursor = db.cursor()
    cursor.execute("SELECT clientId FROM location WHERE code = %s", (location_code,))
    result = cursor.fetchone()
    cursor.close()

    if not result:
        return 'UNKNOWN'

    client_id = result[0]

    if client_id is None:
        return 'FREE'
    elif client_id == requesting_client_id:
        return 'YOUR_LOCATION'
    else:
        return 'OCCUPIED'

# Question handlers
def handle_putaway_question(part_id):
    """Answer: Where should I put this part?"""
    cursor = db.cursor()

    # Get part info from database
    cursor.execute('SELECT code, description, clientId FROM part WHERE id = %s', (part_id,))
    result = cursor.fetchone()

    if not result:
        print(f"\nPart {part_id} not found in database.\n")
        cursor.close()
        return

    part_code, desc, client_id = result

    print(f"\n{'='*80}")
    print(f"Part {part_id} ({part_code}) - {desc or 'N/A'}")
    print(f"{'='*80}\n")

    # Load from local knowledge base
    kb_data = load_part_data(part_id)

    if not kb_data:
        print("⚠ No historical pattern found")
        print("  RECOMMENDATION: Consult supervisor\n")
        cursor.close()
        return

    # Check for consolidation opportunity
    inv = kb_data.get('current_inventory', {})
    if inv.get('total_locations', 0) > 0:
        locs = inv.get('locations', [])
        valid_locs = [loc for loc in locs if is_valid_location(loc.get('location_code'))]

        if valid_locs:
            best_loc = valid_locs[0]
            status = check_location_availability(best_loc['location_code'], client_id)

            if status in ['FREE', 'YOUR_LOCATION']:
                print("✓ RECOMMENDED LOCATION: " + best_loc['location_code'])
                print("\nREASON:")
                print("  Consolidate with existing stock")
                print("  This keeps all inventory together")
                print("\nBENEFITS:")
                print("  - Faster picking (one location)")
                print("  - Easier cycle counting")
                print()
                cursor.close()
                return

    # Use historical patterns
    locations = kb_data.get('locations', [])
    if locations:
        valid = [loc for loc in locations if is_valid_location(loc.get('code'))]

        # Check availability
        available = []
        for loc in valid:
            status = check_location_availability(loc['code'], client_id)
            if status in ['FREE', 'YOUR_LOCATION']:
                available.append(loc)

        if available:
            best = available[0]
            total = kb_data.get('total_putaways', 0)

            print("✓ RECOMMENDED LOCATION: " + best['code'])
            print("\nREASON:")
            print(f"  Used {best.get('count', 0)} times out of {total} putaways")
            print(f"  Operators choose this location {best.get('percentage', 0):.1f}% of the time")
            print()

            if len(available) > 1:
                print("ALTERNATIVE LOCATIONS:")
                for alt in available[1:4]:
                    print(f"  - {alt['code']} (used {alt.get('count', 0)}x, {alt.get('percentage', 0):.1f}%)")
                print()
        else:
            print("⚠ All historical locations are currently occupied")
            print("  RECOMMENDATION: Consult supervisor\n")
    else:
        print("⚠ No historical pattern found")
        print("  RECOMMENDATION: Consult supervisor\n")

    cursor.close()

def handle_empty_locations_question(limit=20):
    """Answer: Which locations are empty?"""
    cursor = db.cursor()

    cursor.execute('''
        SELECT code, zone
        FROM location
        WHERE clientId IS NULL
        LIMIT %s
    ''', (limit,))

    results = cursor.fetchall()

    if results:
        print(f"\n{'='*80}")
        print(f"EMPTY LOCATIONS (showing {len(results)})")
        print(f"{'='*80}\n")

        valid_count = 0
        for code, zone in results:
            if is_valid_location(code):
                zone_info = f" (Zone {zone})" if zone else ""
                print(f"  ✓ {code:15}{zone_info}")
                valid_count += 1

        if valid_count == 0:
            print("  No valid empty locations (filtered out FLOOR*, REC*, ORD*, subdivided)")
        print()
    else:
        print("\nNo empty locations found.\n")

    cursor.close()

def handle_location_contents_question(location_code):
    """Answer: What's in this location?"""
    cursor = db.cursor()

    # Check if location exists
    cursor.execute('SELECT id, code, clientId FROM location WHERE code = %s', (location_code,))
    loc_result = cursor.fetchone()

    if not loc_result:
        print(f"\nLocation {location_code} not found.\n")
        cursor.close()
        return

    loc_id, code, client_id = loc_result

    print(f"\n{'='*80}")
    print(f"LOCATION: {code}")
    print(f"{'='*80}\n")

    if client_id is None:
        print("STATUS: EMPTY (Available)\n")
        cursor.close()
        return

    # Get client name
    cursor.execute('SELECT name FROM client WHERE id = %s', (client_id,))
    client_result = cursor.fetchone()
    client_name = client_result[0] if client_result else f"Client {client_id}"

    print(f"STATUS: OCCUPIED by {client_name}\n")

    # Get inventory in this location
    cursor.execute('''
        SELECT p.id, p.code, p.description, i.onHand, i.reserved
        FROM inventory i
        JOIN part p ON i.partId = p.id
        WHERE i.locationId = %s AND i.onHand > 0
    ''', (loc_id,))

    inventory = cursor.fetchall()

    if inventory:
        print("CONTENTS:")
        for part_id, part_code, desc, onhand, reserved in inventory:
            available = onhand - (reserved or 0)
            print(f"  Part {part_id} ({part_code})")
            print(f"    Description: {desc or 'N/A'}")
            print(f"    OnHand: {onhand:,.0f} units (Available: {available:,.0f})")
            print()
    else:
        print("No inventory found (location may be reserved)\n")

    cursor.close()

def handle_client_parts_question(client_id):
    """Answer: What parts belong to this client?"""
    cursor = db.cursor()

    # Get client name
    cursor.execute('SELECT name FROM client WHERE id = %s', (client_id,))
    client_result = cursor.fetchone()

    if not client_result:
        print(f"\nClient {client_id} not found.\n")
        cursor.close()
        return

    client_name = client_result[0]

    # Get parts count
    cursor.execute('SELECT COUNT(*) FROM part WHERE clientId = %s', (client_id,))
    count = cursor.fetchone()[0]

    print(f"\n{'='*80}")
    print(f"CLIENT: {client_name} (ID: {client_id})")
    print(f"{'='*80}\n")
    print(f"Total parts: {count}\n")

    # Show sample parts
    cursor.execute('''
        SELECT id, code, description
        FROM part
        WHERE clientId = %s
        LIMIT 10
    ''', (client_id,))

    parts = cursor.fetchall()

    if parts:
        print("Sample parts:")
        for pid, code, desc in parts:
            print(f"  Part {pid:5} - {code:20} ({desc or 'N/A'})")

        if count > 10:
            print(f"\n  ... and {count - 10} more parts")

    print()
    cursor.close()

def handle_part_info_question(part_id):
    """Answer: Tell me about this part"""
    kb_data = load_part_data(part_id)

    if not kb_data:
        print(f"\nNo information found for Part {part_id}\n")
        return

    print(f"\n{'='*80}")
    print(f"PART {part_id} INFORMATION")
    print(f"{'='*80}\n")

    print(f"Part Code: {kb_data.get('part_code', 'N/A')}")
    print(f"Description: {kb_data.get('description', 'N/A')}")
    print(f"Client: {kb_data.get('client_name', 'N/A')}")

    total = kb_data.get('total_putaways', 0)
    if total > 0:
        print(f"\nHistorical putaways: {total} times")

        locs = kb_data.get('locations', [])
        if locs:
            print("\nMost used locations:")
            for loc in locs[:5]:
                print(f"  {loc.get('code', 'N/A'):10} - {loc.get('count', 0):3}x ({loc.get('percentage', 0):.1f}%)")

    inv = kb_data.get('current_inventory', {})
    if inv.get('total_locations', 0) > 0:
        print(f"\nCurrent inventory: {inv.get('total_onhand', 0):,.0f} units in {inv.get('total_locations', 0)} locations")

    print()

# Main conversation loop
def chat():
    print("="*80)
    print(" " * 20 + "WAREHOUSE ASSISTANT (LOCAL MODE)")
    print("="*80)
    print()
    print("Ask me anything about the warehouse!")
    print("Examples:")
    print("  - 'Where should I put Part 600?'")
    print("  - 'Show me empty locations'")
    print("  - 'What's in location G12G?'")
    print("  - 'What parts does Client 34 have?'")
    print("  - 'Tell me about Part 588'")
    print()
    print("Type 'quit' or 'exit' to stop.")
    print("="*80)

    while True:
        try:
            print()
            question = input("You: ").strip()

            if not question:
                continue

            if question.lower() in ['quit', 'exit', 'q', 'bye']:
                print("\nGoodbye! Happy warehousing! 📦\n")
                break

            # Parse question intent
            question_lower = question.lower()

            # Check for part putaway question
            if 'where' in question_lower and ('put' in question_lower or 'place' in question_lower):
                part_id = extract_part_id(question)
                if part_id:
                    handle_putaway_question(part_id)
                    continue

            # Check for empty locations question
            if 'empty' in question_lower or 'available' in question_lower or 'free' in question_lower:
                if 'location' in question_lower:
                    handle_empty_locations_question()
                    continue

            # Check for location contents question
            if "what's in" in question_lower or ('show' in question_lower and 'location' in question_lower):
                location_code = extract_location_code(question)
                if location_code:
                    handle_location_contents_question(location_code)
                    continue

            # Check for client parts question
            if 'client' in question_lower and 'part' in question_lower:
                client_id = extract_client_id(question)
                if client_id:
                    handle_client_parts_question(client_id)
                    continue

            # Check for part information question
            if 'about' in question_lower or 'tell' in question_lower or 'info' in question_lower:
                part_id = extract_part_id(question)
                if part_id:
                    handle_part_info_question(part_id)
                    continue

            # Default: suggest valid questions
            print("\nI didn't understand that question.")
            print("Try asking:")
            print("  - 'Where should I put Part 600?'")
            print("  - 'Show me empty locations'")
            print("  - 'What's in location G12G?'")
            print("  - 'What parts does Client 34 have?'")
            print("  - 'Tell me about Part 588'\n")

        except KeyboardInterrupt:
            print("\n\nGoodbye! Happy warehousing! 📦\n")
            break
        except Exception as e:
            print(f"\nError: {e}\n")
            print("Please try rephrasing your question.")

if __name__ == "__main__":
    try:
        chat()
    finally:
        db.close()
        print("Database connection closed.")
