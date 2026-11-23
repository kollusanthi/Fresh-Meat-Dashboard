# Premium Fresh Meat Store (updated)

Existing storefront pages and functionality are retained. Updates in this package:
- Added Notifications, Privacy Policy, and Help & Support links/pages under My Account.
- Registration sends a 4-digit OTP to the supplied email address. OTP expires after 5 minutes.
- Replaced SQLite with MySQL.

## 1. Install and configure

```bash
cd premium_meat_store
python -m venv venv
# Windows:
venv\Scripts\activate
pip install -r requirements.txt
```

Create the database in MySQL Workbench or the MySQL command line:

```sql
CREATE DATABASE premium_meat_store CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Copy `.env.example` to `.env` and fill in your MySQL password and Gmail SMTP details.
For Gmail, enable 2-Step Verification and create a Google App Password. Use that 16-character
App Password as `MAIL_PASSWORD`; do not use your normal Gmail password.

## 2. Run

```bash
python app.py
```

Open http://127.0.0.1:5000. Tables and sample products are created automatically on first run.

## Notes
- Keep `.env` private and never upload it to GitHub.
- If email credentials are not configured, registration will show an error instead of displaying a demo OTP.
- Existing SQLite data is not automatically migrated. This app now creates/uses MySQL tables; import old data separately if needed.
