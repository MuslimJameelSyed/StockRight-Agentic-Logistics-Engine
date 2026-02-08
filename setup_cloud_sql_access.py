"""
Cloud SQL Access Setup
Helps you set up credentials and access to your existing Cloud SQL instance

Your Instance Details:
- Name: warehouse-putaway
- IP: 35.198.187.177
- Region: europe-west3
- Database: mydatabase_gdpr (already exists!)
"""

import subprocess
import getpass

INSTANCE_NAME = "warehouse-putaway"
INSTANCE_IP = "35.198.187.177"
DATABASE_NAME = "mydatabase_gdpr"

def run_command(command):
    """Run shell command and return output"""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.stdout, result.stderr, result.returncode
    except Exception as e:
        return "", str(e), 1


def get_my_ip():
    """Get current public IP"""
    try:
        import requests
        response = requests.get('https://api.ipify.org', timeout=5)
        return response.text
    except:
        return None


def main():
    print("="*80)
    print(" " * 15 + "CLOUD SQL ACCESS SETUP - warehouse-putaway")
    print("="*80)
    print()
    print("Instance Details:")
    print(f"  Name:     {INSTANCE_NAME}")
    print(f"  IP:       {INSTANCE_IP}")
    print(f"  Database: {DATABASE_NAME}")
    print()

    print("="*80)
    print("STEP 1: Create Application User")
    print("="*80)
    print()
    print("We'll create a 'warehouse_app' user with read-only access")
    print("This is safer than using root in your application")
    print()

    create_user = input("Create warehouse_app user? (y/n): ").strip().lower()

    if create_user == 'y':
        print()
        print("Enter a strong password for warehouse_app:")
        print("(Password will be hidden while typing)")
        password = getpass.getpass("Password: ")
        password_confirm = getpass.getpass("Confirm password: ")

        if password != password_confirm:
            print("✗ Passwords don't match!")
            return

        print()
        print("Creating user...")

        # Create user
        create_cmd = f'''gcloud sql users create warehouse_app \
            --instance={INSTANCE_NAME} \
            --password="{password}"'''

        stdout, stderr, code = run_command(create_cmd)

        if code == 0:
            print("✓ User 'warehouse_app' created!")
            print()
            print("Now granting SELECT permissions on tables...")

            # Grant permissions via SQL
            grant_sql = f'''USE {DATABASE_NAME};
GRANT SELECT ON {DATABASE_NAME}.part TO 'warehouse_app'@'%';
GRANT SELECT ON {DATABASE_NAME}.location TO 'warehouse_app'@'%';
FLUSH PRIVILEGES;'''

            print()
            print("To grant permissions, run this in Cloud Shell:")
            print()
            print("gcloud sql connect warehouse-putaway --user=root")
            print()
            print("Then run:")
            print(grant_sql)
            print()
            print(f"✓ Saved password for warehouse_app: {password}")
            print("  (Write this down!)")
            print()

        else:
            if "already exists" in stderr.lower():
                print("✓ User 'warehouse_app' already exists")
                print(f"  Using password: {password}")
                print()
            else:
                print(f"✗ Error creating user: {stderr}")
                return

    print()
    print("="*80)
    print("STEP 2: Whitelist Your IP Address")
    print("="*80)
    print()
    print("To connect from Python, we need to whitelist your IP")
    print()

    my_ip = get_my_ip()
    if my_ip:
        print(f"Your current IP: {my_ip}")
        print()
        whitelist = input(f"Whitelist {my_ip}? (y/n): ").strip().lower()

        if whitelist == 'y':
            print()
            print("Adding to authorized networks...")

            whitelist_cmd = f'''gcloud sql instances patch {INSTANCE_NAME} \
                --authorized-networks={my_ip}/32 \
                --quiet'''

            stdout, stderr, code = run_command(whitelist_cmd)

            if code == 0:
                print(f"✓ IP {my_ip} whitelisted!")
                print("  Wait 1-2 minutes for changes to apply")
            else:
                print(f"✗ Error: {stderr}")
                print()
                print("Add manually:")
                print(f"1. Go to: https://console.cloud.google.com/sql/instances/{INSTANCE_NAME}/connections")
                print("2. Under 'Authorized networks', click 'ADD NETWORK'")
                print(f"3. Add: {my_ip}/32")
    else:
        print("Could not detect your IP automatically")
        print()
        print("Add manually:")
        print("1. Find your IP: https://whatismyipaddress.com")
        print(f"2. Go to: https://console.cloud.google.com/sql/instances/{INSTANCE_NAME}/connections")
        print("3. Under 'Authorized networks', click 'ADD NETWORK'")
        print("4. Add: YOUR_IP/32")

    print()
    print("="*80)
    print("STEP 3: Test Connection")
    print("="*80)
    print()
    print("Update test_cloud_connection.py with:")
    print(f"  CLOUD_SQL_IP = '{INSTANCE_IP}'")
    print(f"  USER = 'warehouse_app'  (or 'root' if you didn't create warehouse_app)")
    print(f"  PASSWORD = '[your password]'")
    print()
    print("Then run:")
    print("  python test_cloud_connection.py")
    print()

    print()
    print("="*80)
    print("STEP 4: Check if Tables Are Imported")
    print("="*80)
    print()
    print("Let's check if your part and location tables are already in Cloud SQL")
    print()

    check_tables = input("Check tables now? (requires root password) (y/n): ").strip().lower()

    if check_tables == 'y':
        print()
        print("Connecting to Cloud SQL...")
        print("(You'll be prompted for root password)")
        print()

        check_cmd = f'''gcloud sql connect {INSTANCE_NAME} --user=root --database={DATABASE_NAME}'''
        print(f"Running: {check_cmd}")
        print()
        print("Once connected, run:")
        print("  SHOW TABLES;")
        print("  SELECT COUNT(*) FROM part;")
        print("  SELECT COUNT(*) FROM location;")
        print()
        print("If tables exist with data, you're all set!")
        print("If not, you need to import using the exported SQL files")
        print()

        input("Press Enter to open connection...")
        subprocess.run(check_cmd, shell=True)

    print()
    print("="*80)
    print("SUMMARY - Your Credentials")
    print("="*80)
    print()
    print("Save these for your application:")
    print()
    print(f"  CLOUD_SQL_IP:  {INSTANCE_IP}")
    print(f"  DATABASE:      {DATABASE_NAME}")
    print(f"  USER:          warehouse_app (or root)")
    print(f"  PASSWORD:      [the password you set]")
    print()
    print("Use these in:")
    print("  - test_cloud_connection.py")
    print("  - warehouse_chat_cloud_sql.py")
    print()
    print("="*80)
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nCancelled by user")
    except Exception as e:
        print(f"\n\nError: {e}")

    input("\nPress Enter to exit...")
