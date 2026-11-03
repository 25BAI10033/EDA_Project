"""Vercel Serverless Function Entrypoint for Data Detective API.

Exposes the FastAPI 'app' ASGI instance to Vercel's Python runtime.
"""

import os
import sys

# Ensure the project root directory is on Python's module search path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Configure Matplotlib writable directory for serverless environments (AWS Lambda / Vercel)
os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib")

from backend.main import app

