import os
from pathlib import Path

from dotenv import load_dotenv

# project root (two levels up from this file's parent "app")
ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

API_TOKEN = os.getenv("CLASH_API_TOKEN", "")
# tags are shown in-game with a leading #, but it's easy to drop when pasting
MY_TAG = os.getenv("MY_PLAYER_TAG", "").strip()
if MY_TAG and not MY_TAG.startswith("#"):
    MY_TAG = f"#{MY_TAG}"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{ROOT / 'royalecoach.db'}")
# hosts like Render hand out postgres:// URLs; SQLAlchemy 2 wants postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
