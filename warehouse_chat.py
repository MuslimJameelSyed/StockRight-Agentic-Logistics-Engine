"""
WAREHOUSE PUTAWAY RECOMMENDATION SYSTEM

Simple interactive system that answers: "Where should I put Part X?"

Uses:
- Qdrant for historical patterns
- MySQL for real-time location availability

Example:
  You: Where should I put Part 600?
  System: Put it in TP03D - used 3 times before (currently FREE)
"""

import mysql.connector
from qdrant_client import QdrantClient
import re

# Initialize
print("Connecting to Qdrant...")
qdrant = QdrantClient(
    url="https://3fe373b5-8102-4a28-ad88-7bcc9220a6de.europe-west3-0.gcp.cloud.qdrant.io",
    api_key="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.a75jz8gpzkfzNUCCldMQIpUjOvbsJ9QgIjikxX6Kmjk"
)

print("Connecting to database...")
db = mysql.connector.connect(
    host='localhost',
    port=3307,
    database='mydatabase_gdpr',
    user='root',
    password='rootpassword'
)

print("Ready!\n")


def extract_part_id(text):
    """Extract part ID from text"""
    match = re.search(r'\b(?:part\s+)?(\d{1,5})\b', text, re.IGNORECASE)
    if match:
        return int(match.group(1))
    return None


def is_valid_location(location_code):
    """Filter invalid locations (temporary/virtual locations)"""
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


def get_location_status(location_code, client_id):
    """Check if location is FREE or OCCUPIED"""
    cursor = db.cursor()
    cursor.execute("SELECT clientId FROM location WHERE code = %s", (location_code,))
    result = cursor.fetchone()
    cursor.close()

    if not result:
        return "UNKNOWN"

    loc_client_id = result[0]

    # FREE if empty OR owned by same client
    if loc_client_id is None or loc_client_id == client_id:
        return "FREE"
    else:
        return "OCCUPIED"


def recommend_location(part_id):
    """Main recommendation function"""
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
    print(f"PUTAWAY RECOMMENDATION FOR PART {part_id}")
    print(f"{'='*80}")
    print(f"Part Code:    {part_code}")
    print(f"Description:  {desc or 'N/A'}")
    print(f"{'='*80}\n")

    # STEP 1: RETRIEVAL - Get historical patterns from Qdrant
    try:
        results = qdrant.retrieve(collection_name='PartSummary', ids=[part_id])

        if not results:
            print("No historical data found for this part.")
            print("RECOMMENDATION: Consult supervisor for first-time putaway.\n")
            cursor.close()
            return

        qdrant_data = results[0].payload

    except Exception as e:
        print(f"Error retrieving from Qdrant: {e}")
        print("RECOMMENDATION: Consult supervisor.\n")
        cursor.close()
        return

    # Get locations from Qdrant
    locations = qdrant_data.get('all_locations', [])
    total_putaways = qdrant_data.get('total_putaways', 0)

    if not locations:
        print("No historical patterns found.")
        print("RECOMMENDATION: Consult supervisor.\n")
        cursor.close()
        return

    # STEP 2: AUGMENTATION - Filter valid locations and check MySQL status
    location_recommendations = []

    for loc in locations:
        loc_code = loc.get('code')

        # Filter out invalid locations
        if not is_valid_location(loc_code):
            continue

        # Get current status from MySQL
        status = get_location_status(loc_code, client_id)

        # Only recommend if FREE
        if status == "FREE":
            location_recommendations.append({
                'code': loc_code,
                'count': loc.get('count', 0),
                'percentage': loc.get('percentage', 0),
                'status': status
            })

    # Sort by usage count (most used first)
    location_recommendations.sort(key=lambda x: x['count'], reverse=True)

    # STEP 3: GENERATION - Provide recommendations
    if location_recommendations:
        best = location_recommendations[0]

        print(f">> PUT IT IN: {best['code']}")
        print(f"\nREASON:")
        print(f"  - Used {best['count']} times before (out of {total_putaways} total putaways)")
        print(f"  - Chosen {best['percentage']:.1f}% of the time historically")
        print(f"  - Status: {best['status']}")

        # Show alternatives
        if len(location_recommendations) > 1:
            print(f"\nALTERNATIVE LOCATIONS:")
            for alt in location_recommendations[1:5]:
                print(f"  {alt['code']:<10} - used {alt['count']}x ({alt['percentage']:.1f}%) - {alt['status']}")

        print()

    else:
        print("All historical locations are currently OCCUPIED.")
        print("\nSHOWING TOP HISTORICAL LOCATIONS (even if occupied):")

        # Show top locations regardless of status
        all_valid = [loc for loc in locations if is_valid_location(loc.get('code'))]
        all_valid.sort(key=lambda x: x.get('count', 0), reverse=True)

        for loc in all_valid[:5]:
            loc_code = loc.get('code')
            status = get_location_status(loc_code, client_id)
            print(f"  {loc_code:<10} - used {loc.get('count')}x ({loc.get('percentage', 0):.1f}%) - {status}")

        print("\nRECOMMENDATION: Wait for a location to free up or consult supervisor.\n")

    cursor.close()


def chat():
    """Main interactive loop"""
    print("="*80)
    print(" " * 20 + "WAREHOUSE PUTAWAY ASSISTANT")
    print("="*80)
    print()
    print("Ask me where to put parts!")
    print()
    print("Examples:")
    print("  - Where should I put Part 600?")
    print("  - Part 14")
    print("  - 223")
    print()
    print("Type 'quit' to exit.")
    print("="*80)

    while True:
        try:
            print()
            question = input("You: ").strip()

            if not question:
                continue

            if question.lower() in ['quit', 'exit', 'q', 'bye']:
                print("\nGoodbye!\n")
                break

            # Extract part ID from question
            part_id = extract_part_id(question)

            if part_id:
                recommend_location(part_id)
            else:
                print("\nPlease specify a part ID (e.g., 'Part 600' or just '600')\n")

        except KeyboardInterrupt:
            print("\n\nGoodbye!\n")
            break
        except Exception as e:
            print(f"\nError: {e}\n")


if __name__ == "__main__":
    try:
        chat()
    finally:
        db.close()
        print("Database connection closed.")
