"""Constants, paths, and local config persistence."""

import json
import os
from pathlib import Path

APP_NAME = "AI Text Humanizer"

if os.name == "nt":
    CONFIG_DIR = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "AITextHumanizer"
else:
    CONFIG_DIR = Path.home() / ".config" / "AITextHumanizer"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
DEEPSEEK_MODEL = "deepseek-chat"
# If a configured model ID is rejected with 404/model-not-found, retry with this
# one and log a warning. Kept equal to the current default so the fallback only
# kicks in when DEEPSEEK_MODEL is changed.
DEEPSEEK_FALLBACK_MODEL = "deepseek-chat"

DEFAULT_CHAIN = ["zh-CN", "ja", "ar", "ru"]
DEFAULT_TEMPERATURE = 1.3
TRANSLATE_LANGUAGES = ["zh-CN", "ja", "ar", "ru", "ko", "tr", "de", "fr"]

MAX_CHUNK_WORDS = 1200
TRANSLATE_RETRIES = 3
LLM_RETRIES = 3
MIN_LEN_RATIO = 0.40
MAX_LEN_RATIO = 2.50

MIN_INPUT_WORDS = 50
LLM_TIMEOUT_SECONDS = 120.0
LLM_BACKOFF_SECONDS = (2, 4, 8)
TRANSLATE_BACKOFF_SECONDS = 1.5
TRANSLATE_HOP_DELAY_SECONDS = 0.6

STRIP_TEMPERATURE = 0.7
VERIFY_TEMPERATURE = 0.2


def load_config() -> dict:
    """Read the local config file. Returns an empty dict on any failure."""
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_config(values: dict) -> None:
    """Merge values into the config file and restrict it to the current user."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = load_config()
    data.update(values)
    with open(CONFIG_FILE, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
    try:
        os.chmod(CONFIG_FILE, 0o600)
    except OSError:
        pass
