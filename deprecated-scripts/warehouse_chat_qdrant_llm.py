"""
WAREHOUSE PUTAWAY RECOMMENDATION SYSTEM - QDRANT + CLOUD SQL + LLM VERSION

Uses:
- Qdrant for historical patterns
- Cloud SQL for real-time location availability
- Ollama (Mistral) for natural language explanations

Example:
  You: Where should I put Part 600?
  System: I recommend location TP03D because this part has historically been
          placed there 3 times (5.66% of all putaways). The location is currently
          FREE and available for use.
"""

import mysql.connector
from qdrant_client import QdrantClient
import sys
import json
import google.generativeai as genai

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

# Initialize Gemini (Google AI)
print("Connecting to Gemini AI...")
genai.configure(api_key="AIzaSyDAzKSYt018agrc_1RIAoFTWU5sSsv_k0E")
gemini_model = genai.GenerativeModel('gemini-2.5-flash')

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


def generate_llm_explanation(recommendation_data):
    """
    Use Gemini to generate natural language explanation for the recommendation

    Args:
        recommendation_data: Dict with recommendation details

    Returns:
        String with LLM-generated explanation
    """
    usage_pct = recommendation_data['usage_percentage']
    usage_count = recommendation_data['usage_count']
    location = recommendation_data['recommended_location']

    # Smart prompt based on usage frequency
    if usage_pct >= 50:
        # High confidence - majority of times
        emphasis = "most preferred location"
        detail = f"used for majority ({usage_pct:.1f}%) of putaways"
    elif usage_pct >= 20:
        # Good confidence - frequently used
        emphasis = "frequently used location"
        detail = f"commonly used ({usage_pct:.1f}% of times)"
    elif usage_count >= 5:
        # Moderate confidence - used multiple times
        emphasis = "historically used location"
        detail = f"previously used multiple times"
    else:
        # Low confidence - minimal history
        emphasis = "available location from historical patterns"
        detail = "based on available historical data"

    prompt = (
        f"You are a warehouse management assistant. "
        f"Part '{recommendation_data['part_code']}' for client '{recommendation_data['client_name']}' needs to be stored in the warehouse. "
        f"Location '{location}' is the {emphasis} for this part ({detail}) and is currently FREE and available for immediate use. "
        f"\n\nWrite a clear, confident recommendation in 1-2 sentences that: "
        f"1. States that location {location} is recommended "
        f"2. Emphasizes it is FREE and ready to use RIGHT NOW "
        f"3. Mentions it follows historical patterns (without stating exact numbers) "
        f"Keep it professional and direct."
    )

    try:
        response = gemini_model.generate_content(
            prompt,
            generation_config={
                'temperature': 0.1,
                'max_output_tokens': 1024,
            },
        )

        if response.candidates and len(response.candidates) > 0:
            candidate = response.candidates[0]
            if candidate.content and candidate.content.parts:
                return candidate.content.parts[0].text

        # Fallback based on confidence
        if usage_pct >= 30:
            return f"Location {location} is recommended as it follows the established pattern for this part. The location is currently FREE and ready for immediate use."
        else:
            return f"Location {location} is recommended based on historical usage patterns. The location is currently FREE and available for use."

    except Exception as e:
        # Fallback based on confidence
        if usage_pct >= 30:
            return f"Location {location} is recommended as it follows the established pattern for this part. The location is currently FREE and ready for immediate use."
        else:
            return f"Location {location} is recommended based on historical usage patterns. The location is currently FREE and available for use."


def generate_no_pattern_explanation(part_info):
    """Generate LLM explanation when no historical patterns exist"""
    # Simplified fallback - no LLM needed for this
    zone_info = f"Zone {part_info.get('primary_zone')}" if part_info.get('primary_zone') else "any available zone"
    return f"""This part has no historical putaway data. Please consult your supervisor to assign an appropriate location. Consider placing it in {zone_info} based on similar parts."""


# ============================================================================
# MAIN RECOMMENDATION FUNCTION
# ============================================================================

def recommend_putaway(part_id):
    """Main recommendation function with LLM-powered explanations"""

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
    print("PUTAWAY RECOMMENDATION (LLM-Powered)")
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
        print("No historical patterns found for this part.")
        print()

        # Generate LLM explanation for new part
        part_info = {
            'part_id': part_id,
            'part_code': part_code,
            'description': description or 'N/A',
            'client_name': client_name,
            'client_id': client_id,
            'primary_zone': None,
            'primary_aisle': None
        }

        print("AI ASSISTANT RECOMMENDATION:")
        print("-" * 80)
        llm_response = generate_no_pattern_explanation(part_info)
        print(llm_response)
        print()
        print("=" * 80)
        cursor.close()
        return

    # Get historical locations from Qdrant
    locations = qdrant_data.get('all_locations', [])

    if not locations:
        print("No historical putaway locations found.")
        print()

        part_info = {
            'part_id': part_id,
            'part_code': part_code,
            'description': description or 'N/A',
            'client_name': client_name,
            'client_id': client_id,
            'primary_zone': qdrant_data.get('primary_zone'),
            'primary_aisle': qdrant_data.get('primary_aisle')
        }

        print("AI ASSISTANT RECOMMENDATION:")
        print("-" * 80)
        llm_response = generate_no_pattern_explanation(part_info)
        print(llm_response)
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

        # Prepare data for LLM
        recommendation_data = {
            'part_id': part_id,
            'part_code': part_code,
            'description': description or 'N/A',
            'client_name': client_name,
            'client_id': client_id,
            'recommended_location': best['code'],
            'status': 'FREE',
            'usage_count': best['count'],
            'total_putaways': total_putaways,
            'usage_percentage': best['percentage'],
            'alternatives': [f"{alt['code']} ({alt['count']}x)" for alt in available_locs[1:4]]
        }

        llm_response = generate_llm_explanation(recommendation_data)

        print("-" * 80)
        print(f"  RECOMMENDED LOCATION: {best['code']}")
        print(f"    Status:           FREE")
        print(f"    Historical Usage: {best['count']}x out of {total_putaways} putaways ({best['percentage']:.1f}%)")
        print()

        if len(available_locs) > 1:
            print("  ALTERNATIVES:")
            for i, alt in enumerate(available_locs[1:4], 1):
                print(f"    {i}. {alt['code']} - {alt['count']}x ({alt['percentage']:.1f}%) - FREE")
            print()

        print(f"  AI SUMMARY: {llm_response}")
        print("-" * 80)
    else:
        print("All historically used locations are currently occupied.")
        print()

        # Generate LLM explanation for occupied scenario
        part_info = {
            'part_id': part_id,
            'part_code': part_code,
            'description': description or 'N/A',
            'client_name': client_name,
            'client_id': client_id,
            'primary_zone': qdrant_data.get('primary_zone'),
            'primary_aisle': qdrant_data.get('primary_aisle')
        }

        print("AI ASSISTANT RECOMMENDATION:")
        print("-" * 80)
        prompt = (
            f"You are a warehouse management assistant. "
            f"All previously used warehouse shelf locations for part '{part_code}' ({description}) "
            f"belonging to client '{client_name}' are currently occupied. "
            f"The preferred warehouse zone is {part_info.get('primary_zone', 'Unknown')}. "
            f"In one sentence, advise the warehouse operator what to do next."
        )

        try:
            response = gemini_model.generate_content(
                prompt,
                generation_config={
                    'temperature': 0.1,
                    'max_output_tokens': 1024,
                }
            )
            # Safe text extraction (response.text raises ValueError on empty parts)
            if response.candidates and response.candidates[0].content and response.candidates[0].content.parts:
                print(response.candidates[0].content.parts[0].text)
            else:
                raise ValueError("Empty response from Gemini")
        except Exception as e:
            print(f"Please consult your supervisor to assign a FREE location.")
            print(f"Suggestion: Look for available locations in Zone {part_info.get('primary_zone', 'N/A')}")

        print()

    print("=" * 80)
    cursor.close()


# ============================================================================
# INTERACTIVE MODE
# ============================================================================

if __name__ == "__main__":
    print()
    print("=" * 80)
    print(" " * 10 + "WAREHOUSE PUTAWAY RECOMMENDATION SYSTEM")
    print(" " * 15 + "(QDRANT + CLOUD SQL + LLM VERSION)")
    print(" " * 20 + "Powered by Google Gemini 2.0")
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
