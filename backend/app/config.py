import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
DATA = Path(os.getenv("VIJU_DATA_DIR", "./data")).resolve()
for folder in ("uploads", "cache", "renders", "print"):
    (DATA / folder).mkdir(parents=True, exist_ok=True)
DB = DATA / "viju.sqlite3"
ADMIN_TOKEN = os.getenv("VIJU_ADMIN_TOKEN", "")
TMDB_TOKEN = os.getenv("TMDB_API_TOKEN", "")
PRINTER_BACKEND = os.getenv("PRINTER_BACKEND", "mock")
DEFAULT_MAC = os.getenv("SPROCKET_BLUETOOTH_MAC", "")
DEFAULT_CHANNEL = int(os.getenv("SPROCKET_OBEX_CHANNEL", "4"))
TIMEOUT = int(os.getenv("PRINTER_TIMEOUT_SECONDS", "90"))
WIDTH = int(os.getenv("PRINT_WIDTH", "600"))
HEIGHT = int(os.getenv("PRINT_HEIGHT", "900"))
QUALITY = int(os.getenv("PRINT_JPEG_QUALITY", "92"))
NETWORK_HELPER = os.getenv("VIJU_NETWORK_HELPER", "")
