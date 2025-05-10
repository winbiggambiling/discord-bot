import os
from main import app

# This file is required for gunicorn to work correctly with the Flask app
# It simply imports and exposes the Flask app from main.py

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
