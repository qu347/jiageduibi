import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_DATABASE_URL = os.environ.get(
    "PRICE_COMPARE_DATABASE_URL",
    f"sqlite:///{(DATA_DIR / 'price_compare.db').as_posix()}",
)
