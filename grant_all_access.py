"""
Grant ALL privileges to muslim user on Cloud SQL
"""

import mysql.connector

# Use root or an admin user to grant permissions
ADMIN_CONFIG = {
    'host': '35.198.187.177',
    'port': 3306,
    'database': 'mydatabase_gdpr',
    'user': 'root',  # We'll use root to grant permissions
    'password': input("Enter root password: ").strip()
}

print("="*80)
print("GRANTING ALL PRIVILEGES TO 'muslim' USER")
print("="*80)
print()

try:
    print("Connecting to Cloud SQL as root...")
    conn = mysql.connector.connect(**ADMIN_CONFIG)
    print("✓ Connected!")
    print()

    cursor = conn.cursor()

    # Grant ALL privileges on the database
    print("Granting ALL privileges on mydatabase_gdpr.*...")
    cursor.execute("GRANT ALL PRIVILEGES ON mydatabase_gdpr.* TO 'muslim'@'%'")
    print("✓ Granted!")

    # Apply changes
    print("Flushing privileges...")
    cursor.execute("FLUSH PRIVILEGES")
    print("✓ Done!")
    print()

    # Verify
    print("Verifying permissions for 'muslim':")
    cursor.execute("SHOW GRANTS FOR 'muslim'@'%'")
    grants = cursor.fetchall()

    print()
    for grant in grants:
        print(f"  {grant[0]}")

    cursor.close()
    conn.close()

    print()
    print("="*80)
    print("SUCCESS! User 'muslim' now has ALL privileges")
    print("="*80)
    print()
    print("The muslim user can now:")
    print("  ✓ SELECT (read data)")
    print("  ✓ INSERT (add data)")
    print("  ✓ UPDATE (modify data)")
    print("  ✓ DELETE (remove data)")
    print("  ✓ CREATE (make tables)")
    print("  ✓ DROP (delete tables)")
    print("  ✓ And more...")
    print()

except mysql.connector.Error as e:
    print(f"✗ Error: {e}")
    print()
    print("Make sure:")
    print("  1. Root password is correct")
    print("  2. Your IP is whitelisted (103.72.86.53)")
    print("  3. Cloud SQL instance is running")

except Exception as e:
    print(f"✗ Unexpected error: {e}")

input("\nPress Enter to exit...")
