# 🛡️ bitwarden-1password-totp-patcher

A command-line utility for safely migrating Time-based One-Time Password (TOTP) secrets from a **Bitwarden JSON export** directly into corresponding items in a **1Password vault**.

This script bypasses common import failures by leveraging the `op` CLI to surgically patch the TOTP fields, ensuring they are correctly saved as functional **OTP** generators instead of static text fields.

---

## ✨ Features

* **Surgical Patching:** Updates only the `one-time password` field in existing 1Password items.
* **Composite Matching:** Matches items by **Title** AND **Username** to prevent incorrect overwrites.
* **Orphan Reporting:** Lists specific Bitwarden items that could not be matched in 1Password.
* **Smart URI Detection:** Correctly handles raw TOTP keys and pre-wrapped `otpauth://` URIs found in the Bitwarden export.
* **Cleanup Mode (`-c`):** Allows deletion of broken/static TOTP fields created by failed prior imports.
* **Dry Run (`-d`):** Safely simulates the update process without making any changes to your vault.

---

## 🛠️ Prerequisites

Before running the script, ensure you have the following installed and configured:

1.  **Python 3:** Required to execute the script.
2.  **1Password CLI (`op`):** Must be installed, configured, and authenticated to your vault.
    * *Windows/macOS:* Ensure you have enabled the "Connect with 1Password CLI" setting in your 1Password desktop application.
    * *Authentication:* Run `op signin` once before running the script.
3.  **Bitwarden Export File:** You must use the **unencrypted JSON export** of your vault, as the script needs plaintext access to the secret keys.

---

## ⚠️ Security Warning

**This script requires an unencrypted export file containing all your passwords and secrets.**

* **Backup First:** Before running, ensure you have a recent backup of your 1Password vault.
* **Delete Immediately:** The script must be deleted immediately after use.
* **Live Mode:** Running without `-d` will **overwrite** the `one-time password` field for any matching item found in your vault.

---

## 🚀 Usage

Execute the script using the following commands. Replace `bitwarden_export.json` with your actual file path.

### 1. Dry Run (Simulate)

Always run this first to ensure item titles match correctly before modifying your vault.

```bash
python bw2op_totp.py -f bitwarden_export.json -d
```

### 2. Cleanup (Optional, but Recommended if a previous import failed)

Use this mode to delete the broken `CONCEALED` fields created by earlier failed imports.

```bash
python bw2op_totp.py -f bitwarden_export.json -c
```

### 3. Live Migration (Patching)

Runs the actual update, patching the correct `otpauth://` URI into the targeted 1Password items.

```bash
python bw2op_totp.py -f bitwarden_export.json
```
