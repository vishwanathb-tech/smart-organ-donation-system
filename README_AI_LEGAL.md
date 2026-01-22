Assistant updates:
- Added ai_matcher.py (ML fallback to rule-based).
- Added e-Consent pages and routes to capture digital consent for living donors.
- Added train_model.py to generate model.pkl for testing.
Run steps:
1) pip install -r requirements.txt
2) python train_model.py  # optional, creates model.pkl
3) python app.py
Visit /donor/consent to test e-Consent.
