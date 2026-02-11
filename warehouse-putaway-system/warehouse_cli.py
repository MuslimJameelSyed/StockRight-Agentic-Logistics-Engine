"""
Warehouse Putaway Recommendation System
AI-powered location recommendations based on historical patterns and current availability
"""

import mysql.connector
from qdrant_client import QdrantClient
import sys
import json
import requests
from typing import Optional, Dict, Any

from config import config, ConfigurationError

def retry_on_failure(max_retries=3, delay=1.0):
    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise
            return None
        return wrapper
    return decorator

class SimpleAuditLogger:
    def log_recommendation(self, **kwargs):
        pass

audit_logger = SimpleAuditLogger()

class OllamaClient:
    def __init__(self, base_url: str, model: str, timeout: int = 60):
        self.base_url = base_url
        self.model = model
        self.timeout = timeout
        self.generate_url = f"{base_url}/api/generate"

    def is_available(self) -> bool:
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception:
            return False

    def check_model(self) -> bool:
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get('models', [])
                return any(m.get('name', '').startswith(self.model) for m in models)
            return False
        except Exception:
            return False

    def generate(self, prompt: str, system_prompt: str = None, temperature: float = 0.1,
                 max_tokens: int = 1024) -> Optional[str]:
        try:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens
                }
            }

            if system_prompt:
                payload["system"] = system_prompt

            response = requests.post(self.generate_url, json=payload, timeout=self.timeout)

            if response.status_code == 200:
                result = response.json()
                return result.get('response', '').strip()
            else:
                print(f"Ollama error: {response.status_code} - {response.text}")
                return None

        except requests.exceptions.Timeout:
            print("Ollama request timed out")
            return None
        except Exception as e:
            print(f"Ollama error: {e}")
            return None

print("=" * 80)
print("WAREHOUSE PUTAWAY RECOMMENDATION SYSTEM")
print("=" * 80)
print()

print("Connecting to Qdrant Cloud API...")
try:
    qdrant = QdrantClient(
        url=config.QDRANT_URL,
        api_key=config.QDRANT_API_KEY
    )
    print(f"[OK] Connected to Qdrant: {config.QDRANT_URL}")
except Exception as e:
    print(f"[ERROR] Failed to connect to Qdrant: {e}")
    sys.exit(1)

print("\nConnecting to MySQL...")
try:
    db = mysql.connector.connect(**config.get_db_config())
    print(f"[OK] Connected to MySQL: {config.MYSQL_HOST}:{config.MYSQL_PORT}/{config.MYSQL_DATABASE}")
except Exception as e:
    print(f"[ERROR] Failed to connect to MySQL: {e}")
    print("  Make sure Docker containers are running: docker-compose up -d")
    sys.exit(1)

print("\nConnecting to Ollama...")
ollama_config = config.get_ollama_config()
ollama = OllamaClient(
    base_url=ollama_config['base_url'],
    model=ollama_config['model'],
    timeout=ollama_config['timeout']
)

if not ollama.is_available():
    print(f"[ERROR] Ollama server not running at {ollama_config['base_url']}")
    print("  Make sure Docker containers are running: docker-compose up -d")
    sys.exit(1)

print(f"[OK] Connected to Ollama: {ollama_config['base_url']}")

if not ollama.check_model():
    print(f"[WARNING] Model '{ollama_config['model']}' not found. Downloading...")
    print(f"  Run: docker exec warehouse-ollama ollama pull {ollama_config['model']}")
    sys.exit(1)

print(f"[OK] Model '{ollama_config['model']}' is available")
print()
print("=" * 80)
print("System Ready")
print("=" * 80)
print()

def is_valid_location(location_code):
    if not location_code:
        return False
    if location_code.startswith('FLOOR') or location_code.startswith('REC') or location_code.startswith('ORD'):
        return False
    if len(location_code) >= 2:
        last_two = location_code[-2:]
        if last_two.isalpha() and last_two[0] == last_two[1]:
            return False
    return True

def check_location_availability(location_code, cursor):
    cursor.execute("SELECT clientId FROM location WHERE code = %s", (location_code,))
    result = cursor.fetchone()
    if not result:
        return 'UNKNOWN'
    client_id = result[0]
    return 'FREE' if client_id is None else 'OCCUPIED'

@retry_on_failure(max_retries=config.MAX_RETRIES, delay=1.0)
def get_part_from_qdrant(part_id):
    try:
        results = qdrant.retrieve(
            collection_name=config.QDRANT_COLLECTION_NAME,
            ids=[part_id]
        )
        if results:
            return results[0].payload
        return None
    except Exception as e:
        print(f"Qdrant error: {e}")
        return None

def generate_llm_explanation(recommendation_data: Dict[str, Any]) -> str:
    usage_pct = recommendation_data['usage_percentage']
    usage_count = recommendation_data['usage_count']
    location = recommendation_data['recommended_location']
    part_code = recommendation_data['part_code']
    client_name = recommendation_data['client_name']

    if usage_pct >= 50:
        emphasis = "most preferred location"
        detail = f"used for majority ({usage_pct:.1f}%) of putaways"
    elif usage_pct >= 20:
        emphasis = "frequently used location"
        detail = f"commonly used ({usage_pct:.1f}% of times)"
    elif usage_count >= 5:
        emphasis = "historically used location"
        detail = f"previously used multiple times"
    else:
        emphasis = "available location from historical patterns"
        detail = "based on available historical data"

    system_prompt = """You are an expert warehouse management assistant. Provide clear, direct recommendations for warehouse storage. Be professional and concise. Do not mention costs or pricing."""

    user_prompt = f"""Part '{part_code}' for client '{client_name}' needs warehouse storage.

Location '{location}' is the {emphasis} for this part ({detail}) and is currently FREE and available for immediate use.

Write a clear, professional recommendation in 1-2 sentences:
- State that location {location} is recommended
- Emphasize it is FREE and ready to use now
- Mention it follows historical patterns

Be direct and professional. Do not mention cost, pricing, or "no additional cost"."""

    try:
        response = ollama.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=config.OLLAMA_TEMPERATURE,
            max_tokens=config.OLLAMA_MAX_TOKENS
        )

        if response:
            return response

        # Fallback based on confidence
        if usage_pct >= 30:
            return f"Location {location} is recommended as it follows the established pattern for this part. The location is currently FREE and ready for immediate use."
        else:
            return f"Location {location} is recommended based on historical usage patterns. The location is currently FREE and available for use."

    except Exception as e:
        print(f"LLM generation error: {e}")
        # Fallback based on confidence
        if usage_pct >= 30:
            return f"Location {location} is recommended as it follows the established pattern for this part. The location is currently FREE and ready for immediate use."
        else:
            return f"Location {location} is recommended based on historical usage patterns. The location is currently FREE and available for use."


def generate_no_pattern_explanation(part_info: Dict[str, Any]) -> str:
    """Generate LLM explanation when no historical patterns exist"""
    zone_info = f"Zone {part_info.get('primary_zone')}" if part_info.get('primary_zone') else "any available zone"

    system_prompt = """You are a professional warehouse management assistant. Be concise and direct. Provide guidance in exactly 1-2 short sentences."""

    user_prompt = f"""Part has no historical putaway data. In 1-2 short sentences: tell the operator to consult their supervisor for placement and mention {zone_info} as an option. Be brief and professional."""

    response = ollama.generate(
        prompt=user_prompt,
        system_prompt=system_prompt,
        temperature=0.1,
        max_tokens=100
    )

    if response:
        return response

    return f"No historical putaway data available. Consult your supervisor for placement guidance — consider {zone_info}."


# ============================================================================
# MAIN RECOMMENDATION FUNCTION
# ============================================================================

def recommend_putaway(part_id):
    """Main recommendation function with Ollama-powered explanations"""

    cursor = db.cursor()

    # Get part info from MySQL
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

    if not qdrant_data or not qdrant_data.get('all_locations'):
        print("No historical patterns found for this part.")
        print()

        part_info = {
            'part_id': part_id,
            'part_code': part_code,
            'description': description or 'N/A',
            'client_name': client_name,
            'client_id': client_id,
            'primary_zone': qdrant_data.get('primary_zone') if qdrant_data else None
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

    # Filter valid locations and check availability
    available_locs = []

    for loc in locations:
        loc_code = loc.get('code')
        if not is_valid_location(loc_code):
            continue

        status = check_location_availability(loc_code, cursor)

        if status == 'FREE':
            available_locs.append({
                'code': loc_code,
                'count': loc.get('count', 0),
                'percentage': loc.get('percentage', 0),
                'status': status
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
            'usage_percentage': best['percentage']
        }

        print("Generating AI recommendation...")
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

        # Audit logging
        audit_logger.log_recommendation(
            part_id=part_id,
            part_code=part_code,
            recommended_location=best['code'],
            status='FREE',
            usage_count=best['count'],
            usage_percentage=best['percentage'],
            alternatives=[a['code'] for a in available_locs[1:4]]
        )

    else:
        print("All historically used locations are currently occupied.")
        print()

        part_info = {
            'part_code': part_code,
            'description': description or 'N/A',
            'client_name': client_name,
            'primary_zone': qdrant_data.get('primary_zone', 'Unknown')
        }

        system_prompt = """You are an expert warehouse management assistant. Provide clear guidance when locations are occupied."""

        user_prompt = f"""All previously used warehouse shelf locations for part '{part_code}' ({description}) belonging to client '{client_name}' are currently occupied. The preferred warehouse zone is {part_info.get('primary_zone', 'Unknown')}. In one sentence, advise the warehouse operator what to do next."""

        print("AI ASSISTANT RECOMMENDATION:")
        print("-" * 80)

        llm_response = ollama.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
            temperature=0.1,
            max_tokens=512
        )

        if llm_response:
            print(llm_response)
        else:
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
    print("WAREHOUSE PUTAWAY RECOMMENDATION SYSTEM")
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
