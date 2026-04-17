"""
Root conftest.py — adds sibling project backend paths to sys.path.

This lets test files do `from app.main import app` etc. without modifying
the source repos.  Each sub-conftest (server_backend/, desktop_backend/)
picks up the correct project depending on which test directory is running.
"""
import os
import sys
from pathlib import Path

# This file lives at:
#   MasterplanOptimiserV3 - Testing/masterplanOptimiserV3---Testing/conftest.py
# Sibling repos are at:
#   MasterplanOptimiserV3 - Server/MasterplanOptimiserV3---Server/backend/
#   MasterplanOptimiserV3 - App/masterplanOptimiserV3 - App/backend/

_THIS_DIR = Path(__file__).resolve().parent
_EYP_ROOT = _THIS_DIR.parent.parent  # …/EYP/

SERVER_BACKEND = _EYP_ROOT / "MasterplanOptimiserV3 - Server" / "MasterplanOptimiserV3---Server" / "backend"
DESKTOP_BACKEND = _EYP_ROOT / "MasterplanOptimiserV3 - App" / "masterplanOptimiserV3 - App" / "backend"

# Set env vars BEFORE any app code is imported
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("WEBAUTHN_RP_ID", "localhost")
os.environ.setdefault("WEBAUTHN_RP_NAME", "Test")
os.environ.setdefault("WEBAUTHN_ORIGIN", "https://localhost")
os.environ.setdefault("DOMAIN", "localhost")
os.environ.setdefault("CORS_ORIGINS", '["https://localhost"]')
os.environ.setdefault("VAPID_PRIVATE_KEY", "")
os.environ.setdefault("VAPID_CLAIMS_EMAIL", "")
