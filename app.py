"""
Smart Organ Donation System - Main Entry Point
This module imports and runs the organ donation Flask application.
All core functionality is in organ_donation_system.py
"""

# Import the main Flask app and run it
from organ_donation_system import app

if __name__ == '__main__':
    app.run(debug=True)
