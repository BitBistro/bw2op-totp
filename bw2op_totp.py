#!/usr/bin/env python3
"""
Bitwarden to 1Password TOTP Patcher
-------------------------------------------------------------------------------
A utility to migrate Time-based One-Time Password (TOTP) secrets from a
Bitwarden JSON export into an existing 1Password vault.

It matches items by TITLE and USERNAME to ensure the correct item is patched,
then updates the item in 1Password using the CLI to ensure the field is
correctly typed as a functional generator.

PREREQUISITES:
  1. 1Password CLI ('op') installed and authenticated.
  2. An UNENCRYPTED Bitwarden JSON export file.
     (WARNING: Delete this file immediately after use).
-------------------------------------------------------------------------------
"""

import json
import subprocess
import sys
import urllib.parse
import argparse
import os

# -----------------------------------------------------------------------------
# CONFIGURATION
# -----------------------------------------------------------------------------
# The 1Password Vault to search (e.g., "Private", "Personal", "Shared")
OP_VAULT_NAME = "Private"
# -----------------------------------------------------------------------------

MIT_LICENSE = """
MIT License

Copyright (c) 2025

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

def get_op_items(vault_name):
    """
    Fetch items from 1Password and build a lookup map.
    Returns a dictionary where Key = Title, Value = List of Item Objects (ID + Username)
    """
    print(f"--> Fetching items from 1Password vault: '{vault_name}'...")
    try:
        subprocess.run(["op", "--version"], capture_output=True, check=True)

        # 'additional_information' usually holds the username for Login items in the list view
        cmd = ["op", "item", "list", "--vault", vault_name, "--format", "json"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        items = json.loads(result.stdout)

        lookup = {}
        for item in items:
            title = item.get('title')
            op_id = item.get('id')
            # 1Password CLI returns the username in 'additional_information' for login items
            username = item.get('additional_information', '')

            # Normalize username to string, handle None
            if username is None:
                username = ""

            if title not in lookup:
                lookup[title] = []

            lookup[title].append({
                'id': op_id,
                'username': username
            })

        return lookup
    except FileNotFoundError:
        print("Error: 'op' command not found. Is the 1Password CLI installed?")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"Error fetching 1Password items: {e.stderr}")
        sys.exit(1)

def construct_otp_url(secret, label):
    """Constructs a standard otpauth URL."""
    secret = secret.strip()

    if secret.lower().startswith("otpauth://"):
        return secret

    clean_secret = secret.replace(" ", "").replace("-", "")
    encoded_label = urllib.parse.quote(label)
    return f"otpauth://totp/{encoded_label}?secret={clean_secret}&issuer=BitwardenMigration"

def find_match(title, bw_username, op_lookup):
    """
    Finds a specific item ID by matching Title AND Username.
    """
    if title not in op_lookup:
        return None

    candidates = op_lookup[title]

    # Normalize Bitwarden username
    target_user = bw_username if bw_username else ""

    for candidate in candidates:
        op_user = candidate['username']
        # Strict string equality for username match
        if op_user == target_user:
            return candidate['id']

    return None

def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Patch missing TOTP secrets from Bitwarden export to 1Password.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
EXAMPLES:
  1. Dry Run (Safe check):
     python %(prog)s -f export.json -d

  2. Cleanup (Remove broken fields from previous attempts):
     python %(prog)s -f export.json -c

  3. Live Migration:
     python %(prog)s -f export.json
        """
    )
    parser.add_argument("-f", "--file", help="Path to the unencrypted Bitwarden JSON export file")
    parser.add_argument("-d", "--dry-run", action="store_true", help="Simulate the action without modifying items")
    parser.add_argument("-c", "--clear", action="store_true", help="DELETE the 'one-time password' field from matched items")
    parser.add_argument("-l", "--license", action="store_true", help="Display the MIT license and exit")

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    return parser.parse_args()

def main():
    args = parse_arguments()

    if args.license:
        print(MIT_LICENSE)
        sys.exit(0)

    if not args.file:
        print("Error: the following arguments are required: -f/--file")
        sys.exit(1)

    if not os.path.exists(args.file):
        print(f"Error: File '{args.file}' not found.")
        sys.exit(1)

    # -------------------------------------------------------------------------
    # SAFETY WARNINGS
    # -------------------------------------------------------------------------
    if not args.dry_run:
        print("\n" + "!"*60)
        print("WARNING: LIVE MODE ACTIVE")
        print("!"*60)
        print("1. Ensure you have backed up your 1Password data before proceeding.")
        if args.clear:
            print("2. You are running in CLEANUP mode (-c).")
            print("   This will PERMANENTLY DELETE the 'one-time password' field")
            print("   from matched items.")
        else:
            print("2. You are running in UPDATE mode.")
            print("   This will OVERWRITE the 'one-time password' field.")

        confirm = input("\nType 'yes' to continue: ")
        if confirm.lower() != 'yes':
            print("Aborted.")
            sys.exit(0)

    # 1. Load Data
    op_lookup = get_op_items(OP_VAULT_NAME)

    try:
        with open(args.file, 'r', encoding='utf-8') as f:
            bw_data = json.load(f)
    except Exception as e:
        print(f"Error reading {args.file}: {e}")
        sys.exit(1)

    mode_label = "DRY RUN" if args.dry_run else "LIVE"
    action_label = "CLEARING/DELETING" if args.clear else "UPDATING"
    print(f"--> Starting {action_label} ({mode_label})...")

    stats = {"found_in_bw": 0, "matched": 0, "success": 0, "fail": 0}
    orphans = []

    items_processed = bw_data.get('items', [])

    for item in items_processed:
        if item.get('login') and item['login'].get('totp'):
            stats['found_in_bw'] += 1

            title = item.get('name')
            bw_username = item.get('login', {}).get('username')

            # Attempt to find match by Title + Username
            op_id = find_match(title, bw_username, op_lookup)

            if op_id:
                stats["matched"] += 1

                # ---------------------------------------------------------
                # MODE: CLEAR (-c)
                # ---------------------------------------------------------
                if args.clear:
                    if args.dry_run:
                        print(f"    [DRY RUN] Would DELETE TOTP for: {title} (User: {bw_username})")
                    else:
                        print(f"    [LIVE] Deleting TOTP for: {title} (User: {bw_username})")
                        try:
                            subprocess.run(
                                ["op", "item", "edit", op_id, "one-time password[delete]"],
                                capture_output=True,
                                text=True,
                                check=True
                            )
                            stats["success"] += 1
                        except subprocess.CalledProcessError as e:
                            if "field not found" in e.stderr:
                                print(f"    [INFO] Field already gone for: {title}")
                            else:
                                print(f"    [FAIL] Could not delete {title}: {e.stderr.strip()}")
                                stats["fail"] += 1

                # ---------------------------------------------------------
                # MODE: UPDATE (Default)
                # ---------------------------------------------------------
                else:
                    totp_secret = item['login']['totp']
                    otp_value = construct_otp_url(totp_secret, title)

                    if args.dry_run:
                        print(f"    [DRY RUN] Would update: {title} (User: {bw_username})")
                    else:
                        print(f"    [LIVE] Updating: {title} (User: {bw_username})")
                        try:
                            subprocess.run(
                                ["op", "item", "edit", op_id, f"one-time password[otp]={otp_value}"],
                                capture_output=True,
                                text=True,
                                check=True
                            )
                            stats["success"] += 1
                        except subprocess.CalledProcessError as e:
                            print(f"    [FAIL] Could not update {title}: {e.stderr.strip()}")
                            stats["fail"] += 1
            else:
                # Track items that did NOT match
                orphans.append(f"{title} (User: {bw_username})")

    # ---------------------------------------------------------
    # SUMMARY
    # ---------------------------------------------------------
    print("\n" + "="*40)
    print(f"SUMMARY ({action_label})")
    print("="*40)
    print(f"Bitwarden Items w/ TOTP: {stats['found_in_bw']}")
    print(f"Items Matched (Title+User): {stats['matched']}")
    if not args.dry_run:
        print(f"Successful Actions:      {stats['success']}")
        print(f"Failed Actions:          {stats['fail']}")
    else:
        print("Mode: DRY RUN (No changes made)")

    if orphans:
        print("-" * 40)
        print("MISSING / UNMATCHED ITEMS:")
        for o in orphans:
            print(f" - {o}")
    print("="*40 + "\n")

if __name__ == "__main__":
    main()
