"""
SIMPLE QDRANT QUERY - No MySQL, just retrieve from Qdrant

Usage: python query_qdrant_simple.py
"""

from qdrant_client import QdrantClient
import json

# Connect to Qdrant
print("Connecting to Qdrant...")
qdrant = QdrantClient(
    url="https://3fe373b5-8102-4a28-ad88-7bcc9220a6de.europe-west3-0.gcp.cloud.qdrant.io",
    api_key="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.a75jz8gpzkfzNUCCldMQIpUjOvbsJ9QgIjikxX6Kmjk"
)
print("Connected!\n")


def query_part(part_id):
    """Query a part from Qdrant by ID"""
    print(f"{'='*80}")
    print(f"QUERYING PART {part_id} FROM QDRANT")
    print(f"{'='*80}\n")

    try:
        # Retrieve from Qdrant
        results = qdrant.retrieve(
            collection_name='PartSummary',
            ids=[part_id]
        )

        if not results:
            print(f"Part {part_id} not found in Qdrant\n")
            return

        # Get the data
        data = results[0].payload

        # Display basic info
        print(f"Part ID:          {data.get('part_id')}")
        print(f"Part Code:        {data.get('part_code')}")
        print(f"Description:      {data.get('part_description', 'N/A')}")
        print(f"Client:           {data.get('client_name', 'N/A')}")
        print(f"Total Putaways:   {data.get('total_putaways', 0)}")
        print(f"Unique Locations: {data.get('unique_locations', 0)}")
        print()

        # Display top locations
        locations = data.get('all_locations', [])
        if locations:
            print("TOP 10 LOCATIONS (by usage):")
            print(f"{'Location':<12} {'Count':<8} {'Percentage':<12} {'First Used':<15} {'Last Used'}")
            print("-" * 80)

            for loc in locations[:10]:
                code = loc.get('code', 'N/A')
                count = loc.get('count', 0)
                pct = loc.get('percentage', 0)
                first = loc.get('first_used_date', 'N/A')
                last = loc.get('last_used_date', 'N/A')

                print(f"{code:<12} {count:<8} {pct:<12.2f} {first:<15} {last}")
        else:
            print("No location history found")

        print("\n")

    except Exception as e:
        print(f"Error querying Qdrant: {e}\n")


def query_part_json(part_id):
    """Query and return raw JSON"""
    print(f"{'='*80}")
    print(f"RAW JSON FOR PART {part_id}")
    print(f"{'='*80}\n")

    try:
        results = qdrant.retrieve(
            collection_name='PartSummary',
            ids=[part_id]
        )

        if results:
            data = results[0].payload
            print(json.dumps(data, indent=2))
        else:
            print(f"Part {part_id} not found")

        print("\n")

    except Exception as e:
        print(f"Error: {e}\n")


# Main script
if __name__ == "__main__":
    print("="*80)
    print(" " * 25 + "QDRANT QUERY TOOL")
    print("="*80)
    print()

    # Example queries
    query_part(14)
    query_part(600)
    query_part(223)

    # Uncomment to see raw JSON:
    # query_part_json(14)

    print("="*80)
    print("QUERY COMPLETE")
    print("="*80)
