"""
PUTAWAY RECOMMENDATION SYSTEM

Simple system that tells where to put an incoming item based on:
1. Current inventory (consolidation priority)
2. Historical patterns
3. Real-time availability

Usage: python putaway_recommendation_system.py <part_id>
"""

import json
import sys
import mysql.connector
import os

# Database connection
conn = mysql.connector.connect(
    host='35.198.187.177',
    port=3306,  # Cloud SQL uses port 3306 (not 3307)
    database='mydatabase_gdpr',
    user='muslim',
    password='Muslim@123'
)

def check_location_availability(location_code, requesting_client_id, cursor):
    """Check if location is available"""
    cursor.execute("SELECT clientId FROM location WHERE code = %s", (location_code,))
    result = cursor.fetchone()

    if not result:
        return 'UNKNOWN', 4

    client_id = result[0]

    if client_id is None:
        return 'FREE', 1
    elif client_id == requesting_client_id:
        return 'YOUR_LOCATION', 1
    else:
        return 'OCCUPIED', 3


def is_valid_location(location_code):
    """
    Filter out invalid locations per client specifications:
    1. FLOOR* - Temporary floor storage
    2. REC* - Receiving virtual locations (removed after receiving)
    3. ORD* - Order/Shipping virtual locations (removed after shipping)
    4. Locations ending in double letters - Subdivided locations (e.g., A02AA, SB08RR)

    Valid formats:
    - Original: XnnY (e.g., A01A, B03A)
    - Zone: ZXnnY (e.g., T01A, SB08R, CA01G)
    """
    if not location_code:
        return False

    # Filter temporary/virtual location prefixes
    if location_code.startswith('FLOOR') or \
       location_code.startswith('REC') or \
       location_code.startswith('ORD'):
        return False

    # Filter subdivided locations ending in double letters (e.g., A02AA, A04AA)
    # Check if last two characters are the same letter
    if len(location_code) >= 2:
        last_two = location_code[-2:]
        if last_two.isalpha() and last_two[0] == last_two[1]:
            return False

    return True


def recommend_putaway(part_id):
    """Main recommendation function"""

    cursor = conn.cursor()

    # Load part data
    # Look for knowledge_base in parent directory
    part_file = f'../knowledge_base/parts/part_{part_id}.json'
    if not os.path.exists(part_file):
        print()
        print("=" * 80)
        print(f"PART {part_id} NOT FOUND IN KNOWLEDGE BASE")
        print("=" * 80)

        # Check if part exists in database
        cursor.execute('SELECT id, code, description, clientId FROM part WHERE id = %s', (part_id,))
        result = cursor.fetchone()

        if result:
            _, code, desc, client_id = result
            print()
            print("Part exists in database but has no recommendation data:")
            print(f"  Part Code: {code}")
            print(f"  Description: {desc or 'N/A'}")
            print(f"  Client ID: {client_id}")
            print()

            # Check why it's not in KB
            cursor.execute('SELECT COUNT(*) FROM receiptdetail WHERE partId = %s', (part_id,))
            putaways = cursor.fetchone()[0]

            print("REASON:")
            if putaways == 0:
                print("  This part has NEVER been received/put away before.")
                print("  No historical patterns exist to learn from.")
            else:
                print(f"  This part has {putaways} historical putaways but wasn't")
                print("  included in knowledge base (may have been filtered).")

            print()
            print(">> RECOMMENDATION: CONSULT SUPERVISOR")
            print()
            print("   Since this is the first time receiving this part,")
            print("   ask your supervisor to assign an appropriate location.")
            print()

            # Show client info if available
            cursor.execute('SELECT name FROM client WHERE id = %s', (client_id,))
            client_result = cursor.fetchone()
            if client_result:
                print(f"   TIP: Check where other parts from {client_result[0]} are stored.")

        else:
            print()
            print(f"Part {part_id} does not exist in the database.")
            print("Please verify the Part ID is correct.")

        print()
        print("=" * 80)
        cursor.close()
        return

    with open(part_file, 'r') as f:
        part_data = json.load(f)

    # Extract part info
    part_code = part_data.get('part_code', 'UNKNOWN')
    description = part_data.get('description') or part_data.get('part_description', 'N/A')
    client_id = part_data.get('client_id')
    client_name = part_data.get('client_name', 'UNKNOWN')

    print()
    print("=" * 80)
    print("PUTAWAY RECOMMENDATION")
    print("=" * 80)
    print(f"Part ID:      {part_id}")
    print(f"Part Code:    {part_code}")
    print(f"Description:  {description}")
    print(f"Client:       {client_name} (ID: {client_id})")
    print("=" * 80)
    print()

    # Check current inventory
    inv = part_data.get('current_inventory', {})
    has_inventory = inv.get('total_locations', 0) > 0

    if has_inventory:
        # STRATEGY 1: CONSOLIDATION - Part has existing inventory
        print("STRATEGY: CONSOLIDATION")
        print("-" * 80)

        # Get primary location with most stock
        inv_locs = inv.get('locations', [])
        if inv_locs:
            # Filter out invalid locations (FLOOR*, REC*, ORD*, double-letter endings)
            valid_inv_locs = [loc for loc in inv_locs if is_valid_location(loc['location_code'])]

            if valid_inv_locs:
                primary_loc = valid_inv_locs[0]

                # Check if primary location is available
                status, priority = check_location_availability(primary_loc['location_code'], client_id, cursor)

                if status in ['FREE', 'YOUR_LOCATION']:
                    print(f">> RECOMMENDED LOCATION: {primary_loc['location_code']}")
                    print()
                    print("REASON:")
                    print("  Consolidate with existing stock")
                    print("  This part is already stored here")
                    print()
                    print("BENEFITS:")
                    print("  - Keeps all inventory together")
                    print("  - Faster picking (one location)")
                    print("  - Easier cycle counting")
                else:
                    # Primary is occupied, try next available
                    found_alternative = False
                    for alt_loc in valid_inv_locs[1:]:
                        status, priority = check_location_availability(alt_loc['location_code'], client_id, cursor)
                        if status in ['FREE', 'YOUR_LOCATION']:
                            print(f">> RECOMMENDED LOCATION: {alt_loc['location_code']}")
                            print()
                            print("REASON:")
                            print("  Consolidate with existing stock")
                            print(f"  (Primary location {primary_loc['location_code']} is occupied by another client)")
                            found_alternative = True
                            break

                    if not found_alternative:
                        print("All consolidation locations are occupied")
                        print("Falling back to historical patterns...")
                        print()
                        has_inventory = False  # Fall through to historical strategy
            else:
                print("All current inventory locations are invalid:")
                print("  - FLOOR* (temporary floor storage)")
                print("  - REC* (receiving areas)")
                print("  - ORD* (order staging)")
                print("  - Subdivided locations (ending in AA, BB, etc.)")
                print()
                print("Using historical patterns instead...")
                print()
                has_inventory = False  # Fall through to historical strategy

    if not has_inventory:
        # STRATEGY 2: HISTORICAL PATTERNS - No inventory
        print("STRATEGY: HISTORICAL PATTERNS")
        print("-" * 80)

        # Get historical locations
        locations = part_data.get('locations', [])

        if not locations:
            print(">> RECOMMENDED LOCATION: Consult supervisor")
            print()
            print("REASON:")
            print("  This part has never been put away before")
            print("  No historical pattern exists")
            print()

            # Show zone/aisle preferences if available (handle both schemas)
            zone_dist = part_data.get('zone_distribution', {})
            aisle_dist = part_data.get('aisle_distribution', {})

            # Try old schema if new schema doesn't have distributions
            if not zone_dist:
                primary_patterns = part_data.get('primary_patterns', {})
                if primary_patterns.get('zone'):
                    zone_dist = {primary_patterns['zone']: primary_patterns.get('zone_percentage', 0)}
                if primary_patterns.get('aisle'):
                    aisle_dist = {primary_patterns['aisle']: primary_patterns.get('aisle_percentage', 0)}

            if zone_dist or aisle_dist:
                print("SUGGESTION:")
                if zone_dist:
                    top_zone = max(zone_dist, key=zone_dist.get)
                    zone_pct = zone_dist[top_zone]
                    if zone_pct > 0:
                        print(f"  Look in Zone {top_zone} (similar parts use this zone {zone_pct:.0f}% of the time)")
                if aisle_dist:
                    top_aisle = max(aisle_dist, key=aisle_dist.get)
                    aisle_pct = aisle_dist[top_aisle]
                    if aisle_pct > 0:
                        print(f"  Preferably Aisle {top_aisle} (used {aisle_pct:.0f}% historically)")
            return

        # Filter valid locations and check availability
        available_locs = []

        for loc in locations:
            loc_code = loc.get('code')
            if not is_valid_location(loc_code):
                continue

            status, priority = check_location_availability(loc_code, client_id, cursor)

            if status in ['FREE', 'YOUR_LOCATION']:
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
            total_putaways = part_data.get('total_putaways', 0)

            print(f">> RECOMMENDED LOCATION: {best['code']}")
            print()
            print("REASON:")
            print(f"  Used {best['count']} times out of {total_putaways} total putaways")
            print(f"  This location was chosen {best['percentage']:.1f}% of the time")
            print(f"  Operators prefer this location for this part")
            print()

            # Show alternatives
            if len(available_locs) > 1:
                print("ALTERNATIVE LOCATIONS:")
                for i, alt in enumerate(available_locs[1:4], 2):
                    print(f"  {i}. {alt['code']} - used {alt['count']}x ({alt['percentage']:.1f}%)")
        else:
            print(">> RECOMMENDED LOCATION: Consult supervisor")
            print()
            print("REASON:")
            print("  All historically used locations are currently occupied")
            print()
            print("SUGGESTION:")
            print("  Ask supervisor to assign a location in similar zone/aisle")

    print()
    print("=" * 80)
    cursor.close()


if __name__ == "__main__":
    # Interactive mode - no command line args needed
    print()
    print("=" * 80)
    print(" " * 20 + "WAREHOUSE PUTAWAY RECOMMENDATION SYSTEM")
    print("=" * 80)
    print()

    # Check if part_id provided via command line (backward compatible)
    if len(sys.argv) >= 2:
        try:
            part_id = int(sys.argv[1])
            recommend_putaway(part_id)
            conn.close()
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
        conn.close()
