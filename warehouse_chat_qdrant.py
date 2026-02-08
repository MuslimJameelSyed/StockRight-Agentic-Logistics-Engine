"""
WAREHOUSE PUTAWAY RECOMMENDATION SYSTEM - QDRANT + CLOUD SQL VERSION

Uses:
- Qdrant for historical patterns (instead of local JSON files)
- Cloud SQL for real-time location availability
- Same recommendation logic as putaway_recommendation_system.py

Example:
  You: Where should I put Part 600?
  System: Put it in TN52D - consolidation strategy
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
    """
    Filter out invalid locations:
    1. FLOOR* - Temporary floor storage
    2. REC* - Receiving virtual locations
    3. ORD* - Order/Shipping virtual locations
    4. Locations ending in double letters - Subdivided locations
    """
    if not location_code:
        return False

    # Filter temporary/virtual location prefixes
    if location_code.startswith('FLOOR') or \
       location_code.startswith('REC') or \
       location_code.startswith('ORD'):
        return False

    # Filter subdivided locations ending in double letters
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

    # Only FREE locations (clientId = NULL) are recommended
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


# ============================================================================
# MAIN RECOMMENDATION FUNCTION
# ============================================================================

def recommend_putaway(part_id):
    """Main recommendation function - matches putaway_recommendation_system.py logic"""

    cursor = db.cursor()

    # Get part info from Cloud SQL
    cursor.execute('SELECT id, code, description, clientId FROM part WHERE id = %s', (part_id,))
    result = cursor.fetchone()

    if not result:
        print()
        print("=" * 80)
        print(f"PART {part_id} NOT FOUND IN DATABASE")
        print("=" * 80)
        print()
        print(f"Part {part_id} does not exist in the database.")
        print("Please verify the Part ID is correct.")
        print()
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
    print("PUTAWAY RECOMMENDATION")
    print("=" * 80)
    print(f"Part ID:      {part_id}")
    print(f"Part Code:    {part_code}")
    print(f"Description:  {description or 'N/A'}")
    print(f"Client:       {client_name} (ID: {client_id})")
    print("=" * 80)
    print()

    # RETRIEVAL: Get historical patterns from Qdrant
    qdrant_data = get_part_from_qdrant(part_id)

    if not qdrant_data:
        print("Part not found in Qdrant knowledge base")
        print()
        print("REASON:")
        print("  This part has never been put away before")
        print("  No historical patterns exist to learn from")
        print()
        print(">> RECOMMENDATION: CONSULT SUPERVISOR")
        print()
        print("   Since this is the first time receiving this part,")
        print("   ask your supervisor to assign an appropriate location.")
        print()
        cursor.close()
        return

    # STRATEGY: HISTORICAL PATTERNS - Use past putaway data
    print("STRATEGY: HISTORICAL PATTERNS")
    print("-" * 80)

    # Get historical locations from Qdrant
    locations = qdrant_data.get('all_locations', [])

    if not locations:
        print(">> RECOMMENDED LOCATION: Consult supervisor")
        print()
        print("REASON:")
        print("  This part has never been put away before")
        print("  No historical pattern exists")
        print()

        # Show zone/aisle preferences if available
        primary_zone = qdrant_data.get('primary_zone')
        primary_aisle = qdrant_data.get('primary_aisle')

        if primary_zone or primary_aisle:
            print("SUGGESTION:")
            if primary_zone:
                print(f"  Look in Zone {primary_zone}")
            if primary_aisle:
                print(f"  Preferably Aisle {primary_aisle}")
            print()
            print("DATA SOURCE: FROM QDRANT (pattern analysis)")

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

        print(f">> RECOMMENDED LOCATION: {best['code']}")
        print()
        print("AVAILABILITY STATUS:")
        print("  [FREE] (clientId = NULL in database)")
        print("  Location is available for any client to use")
        print()
        print("REASON:")
        print(f"  Used {best['count']} times out of {total_putaways} total putaways")
        print(f"  This location was chosen {best['percentage']:.1f}% of the time")
        print(f"  Operators prefer this location for this part")
        print()
        print("DATA SOURCE:")
        print("  - Historical pattern: FROM QDRANT")
        print("  - Availability check: FROM CLOUD SQL")
        print()

        # Show alternatives
        if len(available_locs) > 1:
            print("ALTERNATIVE FREE LOCATIONS:")
            for i, alt in enumerate(available_locs[1:4], 1):
                print(f"  {i}. {alt['code']} - used {alt['count']}x ({alt['percentage']:.1f}%) - [FREE]")
            print()
    else:
        print(">> RECOMMENDED LOCATION: Consult supervisor")
        print()
        print("REASON:")
        print("  All historically used locations are currently occupied (clientId is not NULL)")
        print("  We only recommend FREE locations where clientId = NULL")
        print()
        print("SUGGESTION:")
        print("  Ask supervisor to assign a FREE location in similar zone/aisle")
        print()

    print("=" * 80)
    cursor.close()


# ============================================================================
# INTERACTIVE MODE
# ============================================================================

if __name__ == "__main__":
    print()
    print("=" * 80)
    print(" " * 15 + "WAREHOUSE PUTAWAY RECOMMENDATION SYSTEM")
    print(" " * 20 + "(QDRANT + CLOUD SQL VERSION)")
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
