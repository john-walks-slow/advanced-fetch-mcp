import logging
import os
from pathlib import Path


def env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"

DEFAULT_MAX_LENGTH = int(os.getenv("DEFAULT_MAX_LENGTH", "8000"))
INTERVENTION_TIMEOUT_SECONDS = int(os.getenv("INTERVENTION_TIMEOUT_SECONDS", "600"))
INTERVENTION_BUTTON_ID = "advanced-fetch-intervention-done"
DEFAULT_TIMEOUT_SECONDS = float(os.getenv("DEFAULT_TIMEOUT", "10"))
NAVIGATION_TIMEOUT_MS = max(1, int(float(os.getenv("NAVIGATION_TIMEOUT", str(DEFAULT_TIMEOUT_SECONDS))) * 1000))
NETWORK_IDLE_TIMEOUT_MS = max(1, int(float(os.getenv("NETWORK_IDLE_TIMEOUT", str(DEFAULT_TIMEOUT_SECONDS))) * 1000))
STATIC_FETCH_TIMEOUT_SECONDS = max(0.1, float(os.getenv("STATIC_FETCH_TIMEOUT", str(DEFAULT_TIMEOUT_SECONDS))))
ENABLE_PROMPT_EXTRACTION = env_flag("ENABLE_PROMPT_EXTRACTION", True)
PROMPT_INPUT_MAX_CHARS = int(os.getenv("PROMPT_INPUT_MAX_CHARS", "16000"))
MAX_FIND_MATCHES = int(os.getenv("MAX_FIND_MATCHES", "8"))
FIND_SNIPPET_MAX_CHARS = int(os.getenv("FIND_SNIPPET_MAX_CHARS", "240"))

BROWSER_CHANNEL = os.getenv("BROWSER_CHANNEL", "chrome").strip().lower() or "chrome"
BROWSER_PROFILE_DIR = Path(os.getenv(
    "BROWSER_PROFILE_DIR",
    str(Path.home() / ".advanced-fetch-profile")
)).expanduser()
BROWSER_PROFILE_TEMPLATE_DIR = os.getenv("BROWSER_PROFILE_TEMPLATE_DIR", "").strip()

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/146.0.0.0 Safari/537.36 Edg/146.0.0.0"
)
CORE_REMOVE_TAGS = ["script", "style", "head", "noscript", "template"]
MEDIA_REMOVE_TAGS = ["video", "audio", "img", "canvas", "svg", "picture", "source"]

LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
logger = logging.getLogger("AdvancedFetchMCP")
