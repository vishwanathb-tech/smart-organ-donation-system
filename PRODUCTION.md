Smart Organ Donation System — Production Notes
=============================================

This document contains minimal steps to run the Smart Organ Donation System in a production-like environment.

1) Environment

- Copy `.env.example` to `.env` and update secrets (`SECRET_KEY`, `DATABASE_URL`, Twilio keys, etc.).

2) Install dependencies

```bash
python -m pip install -r requirements.txt
```

3) Run with Gunicorn (Linux) or Waitress (Windows)

- Gunicorn (recommended on Linux):

```bash
gunicorn --bind 0.0.0.0:8000 "organ_donation_system:app"
```

- Waitress (Windows-friendly):

```bash
python -m waitress --port=8000 organ_donation_system:app
```

4) Docker (build + run)

```bash
docker build -t smart-organ-donation .
docker run -p 8000:8000 --env-file .env smart-organ-donation
```

5) Notes

- Replace all demo secrets (Twilio keys, admin password) before production.
- Use a proper RDBMS (Postgres/MySQL) for scaling; update `SQLALCHEMY_DATABASE_URI`.
- Set `DEBUG=False` in production and ensure TLS termination via reverse proxy.
