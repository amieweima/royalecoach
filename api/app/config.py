import os
from pathlib import Path

from dotenv import load_dotenv

# project root (two levels up from this file's parent "app")
ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

API_TOKEN = os.getenv("CLASH_API_TOKEN", "")
MY_TAG = os.getenv("MY_PLAYER_TAG", "")
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{ROOT / 'royalecoach.db'}")
