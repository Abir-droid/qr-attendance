import sys
import os

# Ensure the root directory is in Python path to import app.py and templates
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app

# Vercel looks for the WSGI application instance named `app`