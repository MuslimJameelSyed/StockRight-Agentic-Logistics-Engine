"""
WAREHOUSE PUTAWAY RECOMMENDATION SYSTEM - ENHANCED VERSION

Uses:
- Qdrant for historical patterns
- Cloud SQL for real-time location availability
- Enhanced natural language output (no slow LLM calls)

Example:
  You: Where should I put Part 600?
  System: Intelligent recommendation with clear reasoning
"""

import mysql.connector
from qdrant_client import QdrantClient
import sys

# ============================================================================
# CONNECTIONS
# ============================================================================

# Initialize Qdrant (historical patterns)
print("Connecting to Qdrant...")
qdrant = QdrantClient(
    url="https://3fe373b5-8102-4a28-ad88-7bcc9220a6de.europe-west3-0.gcp.cloud.qdrant.io",
    api_key="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.a75jz8gpzkfzNUCCldMQIpUjOvbsJ9QgIjikxX6Kmjk"
)

# Initialize Cloud SQL (real-time data)
print("Connecting to Cloud SQL...")
db = mysql.connector.connect(
    host='35.198.187.177',
    port=3306,
    database='mydatabase_gdpr',
    user='muslim',
    password='Muslim@123'
)

print("Ready!\n")

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def is_valid_location(location_code):
    """Filter out invalid locations"""
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


def check_location_availability(location_code, requesting_client_id, cursor):
    """Check if location is FREE (clientId is NULL) in Cloud SQL"""
    cursor.execute("SELECT clientId FROM location WHERE code = %s", (location_code,))
    result = cursor.fetchone()

    if not result:
        return 'UNKNOWN', 4

    client_id = result[0]

    if client_id is None:
        return 'FREE', 1
    else:
        return 'OCCUPIED', 3


def get_part_from_qdrant(part_id):
    """Retrieve part data from Qdrant by direct ID lookup"""
    try:
        results = qdrant.retrieve(
            collection_name='PartSummary',
            ids=[part_id]
        )

        if results:
            return results[0].payload
        return None
    except Exception as e:
        print(f"Qdrant error: {e}")
        return None


def generate_recommendation_text(best_loc, total_putaways, part_code, description):
    """Generate natural language recommendation"""
    usage_count = best_loc['count']
    usage_pct = best_loc['percentage']

    # Determine pattern strength
    if usage_pct >= 20:
        strength = "very strong"
    elif usage_pct >= 10:
        strength = "strong"
    elif usage_pct >= 5:
        strength = "moderate"
    else:
        strength = "weak"

    text = f"""
RECOMMENDATION SUMMARY:
I recommend placing Part {part_code} ({description}) in location {best_loc['code']}.

REASONING:
• This location shows a {strength} historical pattern
• Used {usage_count} times out of {total_putaways} total putaways ({usage_pct:.1f}%)
• Location is currently FREE (available for immediate use)
• Past operators consistently chose this location for this part

CONFIDENCE: {"High" if usage_pct >= 10 else "Medium" if usage_pct >= 5 else "Low"}
"""
    return text


# ============================================================================
# MAIN RECOMMENDATION FUNCTION
# ============================================================================

def recommend_putaway(part_id):
    """Main recommendation function with enhanced output"""

    cursor = db.cursor()

    # Get part info from Cloud SQL
    cursor.execute('SELECT id, code, description, clientId FROM part WHERE id = %s', (part_id,))
    result = cursor.fetchone()

    if not result:
        print()
        print("=" * 80)
        print(f"PART {part_id} NOT FOUND")
        print("=" * 80)
        print(f"\nPart {part_id} does not exist in the database.")
        print("Please verify the Part ID is correct.\n")
        print("=" * 80)
        cursor.close()
        return

    _, part_code, description, client_id = result

    # Get client name
    cursor.execute('SELECT name FROM client WHERE id = %s', (client_id,))
    client_result = cursor.fetchone()
    client_name = client_result[0] if client_result else f'Client {client_id}'

    print()
    print("=" * 80)
    print("INTELLIGENT PUTAWAY RECOMMENDATION")
    print("=" * 80)
    print(f"Part ID:      {part_id}")
    print(f"Part Code:    {part_code}")
    print(f"Description:  {description or 'N/A'}")
    print(f"Client:       {client_name} (ID: {client_id})")
    print("=" * 80)
    print()

    # Get historical patterns from Qdrant
    qdrant_data = get_part_from_qdrant(part_id)

    if not qdrant_data:
        print("⚠ NO HISTORICAL DATA FOUND")
        print()
        print("This part has never been put away before.")
        print("No historical patterns are available to learn from.")
        print()
        print("ACTION REQUIRED:")
        print("→ Please consult your supervisor to assign an appropriate location.")
        print()
        print("=" * 80)
        cursor.close()
        return

    # Get historical locations
    locations = qdrant_data.get('all_locations', [])

    if not locations:
        print("⚠ NO LOCATION PATTERNS FOUND")
        print()
        primary_zone = qdrant_data.get('primary_zone')
        primary_aisle = qdrant_data.get('primary_aisle')

        if primary_zone or primary_aisle:
            print("SUGGESTION:")
            if primary_zone:
                print(f"  • Look in Zone {primary_zone}")
            if primary_aisle:
                print(f"  • Preferably Aisle {primary_aisle}")
            print()

        print("ACTION REQUIRED:")
        print("→ Consult supervisor for location assignment")
        print()
        print("=" * 80)
        cursor.close()
        return

    # Filter valid locations and check availability
    available_locs = []

    for loc in locations:
        loc_code = loc.get('code')
        if not is_valid_location(loc_code):
            continue

        status, priority = check_location_availability(loc_code, client_id, cursor)

        if status == 'FREE':
            available_locs.append({
                'code': loc_code,
                'count': loc.get('count', 0),
                'percentage': loc.get('percentage', 0),
                'status': status,
                'priority': priority
            })

    # Sort by historical usage
    available_locs.sort(key=lambda x: -x['count'])

    if available_locs:
        best = available_locs[0]
        total_putaways = qdrant_data.get('total_putaways', 0)

        print("✓ RECOMMENDED LOCATION:", best['code'])
        print()

        # Generate natural language explanation
        explanation = generate_recommendation_text(best, total_putaways, part_code, description or 'N/A')
        print(explanation)

        print("DATA SOURCES:")
        print("  • Historical patterns: Qdrant knowledge base")
        print("  • Availability check: Cloud SQL (real-time)")
        print()

        # Show alternatives
        if len(available_locs) > 1:
            print("ALTERNATIVE FREE LOCATIONS:")
            for i, alt in enumerate(available_locs[1:4], 1):
                print(f"  {i}. {alt['code']} - used {alt['count']}x ({alt['percentage']:.1f}%)")
            print()
    else:
        print("⚠ ALL HISTORICAL LOCATIONS ARE OCCUPIED")
        print()
        print("REASON:")
        print("  All locations where this part was previously stored are currently")
        print("  occupied (clientId is not NULL). We only recommend FREE locations.")
        print()

        primary_zone = qdrant_data.get('primary_zone')
        primary_aisle = qdrant_data.get('primary_aisle')

        print("SUGGESTION:")
        if primary_zone:
            print(f"  • Look for FREE locations in Zone {primary_zone}")
        if primary_aisle:
            print(f"  • Preferably in Aisle {primary_aisle}")
        print()
        print("ACTION REQUIRED:")
        print("→ Consult supervisor to assign a FREE location in similar zone/aisle")
        print()

    print("=" * 80)
    cursor.close()


# ============================================================================
# INTERACTIVE MODE
# ============================================================================

if __name__ == "__main__":
    print()
    print("=" * 80)
    print(" " * 12 + "INTELLIGENT WAREHOUSE PUTAWAY SYSTEM")
    print(" " * 15 + "(Historical Pattern Analysis)")
    print("=" * 80)
    print()

    # Check if part_id provided via command line
    if len(sys.argv) >= 2:
        try:
            part_id = int(sys.argv[1])
            recommend_putaway(part_id)
            db.close()
            sys.exit(0)
        except ValueError:
            print("ERROR: Part ID must be a number")
            sys.exit(1)

    # Interactive mode
    try:
        while True:
            try:
                print("-" * 80)
                part_id_input = input("\nEnter Part ID (or 'q' to quit): ").strip()

                if part_id_input.lower() in ['q', 'quit', 'exit']:
                    print("\nThank you for using Warehouse Recommendation System!")
                    print("=" * 80)
                    break

                if not part_id_input:
                    print("Please enter a valid Part ID")
                    continue

                part_id = int(part_id_input)
                recommend_putaway(part_id)

                # Ask if want to continue
                print()
                continue_choice = input("Check another part? (Y/n): ").strip().lower()
                if continue_choice in ['n', 'no']:
                    print("\nThank you for using Warehouse Recommendation System!")
                    print("=" * 80)
                    break

            except ValueError:
                print("\nERROR: Please enter a valid number")
            except KeyboardInterrupt:
                print("\n\nExiting...")
                print("=" * 80)
                break
            except Exception as e:
                print(f"\nERROR: {e}")

    finally:
        db.close()
        print("\nDatabase connection closed.")
