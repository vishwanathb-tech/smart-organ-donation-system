# Organ Donation System

## Setup Instructions
1. Create virtual environment
   ```bash
   python -m venv venv
   venv\Scripts\activate  # or source venv/bin/activate
   ```
2. Install dependencies
   ```bash
   pip install -r requirements.txt
   ```
3. Run the app
   ```bash
   python organ_donation_system.py
   ```
4. Visit http://127.0.0.1:5000 in your browser.

For production deployment notes, see PRODUCTION.md. Copy `.env.example` to `.env` and update secrets before running in production.
