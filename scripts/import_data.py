"""
Command-line script to initialize the SQLite database and import sales data from CSV.
Usage:
    python scripts/import_data.py [--force] [--reset]
"""

import argparse
import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import init_db, reset_db
from app.data_loader import import_csv_to_db, find_csv_file


def main():
    parser = argparse.ArgumentParser(description="Import sales transactions CSV into SQLite database.")
    parser.add_argument("--force", action="store_true", help="Force re-import even if already imported.")
    parser.add_argument("--reset", action="store_true", help="Reset (drop and recreate) database before import.")
    args = parser.parse_args()

    print("==================================================")
    print("Mini AI BI Assistant - Database Import Pipeline")
    print("==================================================")

    if args.reset:
        print("[*] Resetting database tables...")
        reset_db()
    else:
        init_db()

    try:
        csv_path = find_csv_file()
        print(f"[*] Detected CSV data source: {csv_path.name}")
        
        result = import_csv_to_db(csv_path=csv_path, force_reimport=args.force or args.reset)
        
        print("\n--- Import Summary ---")
        print(f"Status:           {result['status']}")
        print(f"File Name:        {result['filename']}")
        print(f"Total Rows:       {result['total_records']}")
        print(f"Valid Rows:       {result['valid_records']}")
        print(f"Flagged Rows:     {result['flagged_records']}")

        if result.get("flagged_details"):
            print("\n--- Flagged Data-Quality Issues ---")
            for item in result["flagged_details"]:
                print(f"  - [{item['transaction_id']}] Flag: {item.get('flag')} | Reason: {item.get('reason')}")
        
        print("\n[+] Database initialization completed successfully.")
        return 0

    except Exception as e:
        print(f"\n[-] Error during import: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
