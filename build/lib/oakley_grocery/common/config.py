import os
from pathlib import Path

_PACKAGE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("OAKLEY_GROCERY_DATA_DIR", Path.home() / ".oakley-grocery" / "data"))
CACHE_DIR = DATA_DIR / "cache"
DB_PATH = DATA_DIR / "grocery.db"
CONFIG_PATH = DATA_DIR / "config.json"

CACHE_TTL = {
    "search": 3600,        # 1 hour — product search results
    "product": 86400,      # 24 hours — product details
    "specials": 14400,     # 4 hours — specials
    "trolley": 300,        # 5 minutes — trolley status
}

STALE_CACHE_MAX_AGE = 86400  # 24 hours fallback

# Rate limits — Woolworths web API
WOOLWORTHS_RATE_LIMIT_CALLS = 5
WOOLWORTHS_RATE_LIMIT_PERIOD = 1  # 5 req/sec

TELEGRAM_MAX_LENGTH = 4096

TIMEZONE = "Australia/Sydney"

REQUEST_TIMEOUT = 20  # seconds

# Woolworths API
WOOLWORTHS_BASE_URL = "https://www.woolworths.com.au"
WOOLWORTHS_SEARCH_URL = f"{WOOLWORTHS_BASE_URL}/apis/ui/Search/products"
WOOLWORTHS_PRODUCT_URL = f"{WOOLWORTHS_BASE_URL}/apis/ui/product/detail"
WOOLWORTHS_TROLLEY_URL = f"{WOOLWORTHS_BASE_URL}/api/v3/ui/trolley/update"
WOOLWORTHS_TROLLEY_LIST_URL = f"{WOOLWORTHS_BASE_URL}/api/v3/ui/trolley/items"

# Search defaults
DEFAULT_PAGE_SIZE = 10
DEFAULT_SORT = "TraderRelevance"

# Resolver thresholds
AUTO_RESOLVE_MIN_SCORE = 0.4
AUTO_RESOLVE_GAP = 0.1

# Memory defaults
DEFAULT_USUAL_MIN_FREQUENCY = 3
DEFAULT_USUAL_LOOKBACK_ORDERS = 10


class Config:
    """Central access point for all configuration."""

    package_dir = _PACKAGE_DIR
    data_dir = DATA_DIR
    cache_dir = CACHE_DIR
    db_path = DB_PATH
    config_path = CONFIG_PATH

    cache_ttl = CACHE_TTL
    stale_cache_max_age = STALE_CACHE_MAX_AGE

    woolworths_rate_limit_calls = WOOLWORTHS_RATE_LIMIT_CALLS
    woolworths_rate_limit_period = WOOLWORTHS_RATE_LIMIT_PERIOD

    telegram_max_length = TELEGRAM_MAX_LENGTH
    timezone = TIMEZONE
    request_timeout = REQUEST_TIMEOUT

    woolworths_base_url = WOOLWORTHS_BASE_URL
    woolworths_search_url = WOOLWORTHS_SEARCH_URL
    woolworths_product_url = WOOLWORTHS_PRODUCT_URL
    woolworths_trolley_url = WOOLWORTHS_TROLLEY_URL
    woolworths_trolley_list_url = WOOLWORTHS_TROLLEY_LIST_URL

    default_page_size = DEFAULT_PAGE_SIZE
    default_sort = DEFAULT_SORT

    auto_resolve_min_score = AUTO_RESOLVE_MIN_SCORE
    auto_resolve_gap = AUTO_RESOLVE_GAP

    default_usual_min_frequency = DEFAULT_USUAL_MIN_FREQUENCY
    default_usual_lookback_orders = DEFAULT_USUAL_LOOKBACK_ORDERS

    @classmethod
    def ensure_dirs(cls):
        cls.data_dir.mkdir(parents=True, exist_ok=True)
        cls.cache_dir.mkdir(parents=True, exist_ok=True)
