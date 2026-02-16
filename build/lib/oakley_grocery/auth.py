"""Credential management — Woolworths API key + browser cookies."""

from __future__ import annotations

import json
from typing import Optional

from oakley_grocery.common.config import Config


def _load_config() -> dict:
    """Load config from disk."""
    Config.ensure_dirs()
    if not Config.config_path.exists():
        return {}
    try:
        return json.loads(Config.config_path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _save_config(data: dict) -> None:
    """Write config to disk."""
    Config.ensure_dirs()
    Config.config_path.write_text(json.dumps(data, indent=2))


# ─── Woolworths API Key ──────────────────────────────────────────────────────

def save_woolworths_key(api_key: str) -> None:
    """Save Woolworths API key."""
    config = _load_config()
    config["woolworths_api_key"] = api_key
    _save_config(config)


def get_woolworths_key() -> Optional[str]:
    """Return Woolworths API key or None."""
    config = _load_config()
    return config.get("woolworths_api_key") or None


def has_woolworths_key() -> bool:
    return get_woolworths_key() is not None


# ─── Woolworths Cookies (for trolley/cart operations) ────────────────────────

def save_woolworths_cookies(cookies: str) -> None:
    """Save Woolworths browser cookies for cart operations."""
    config = _load_config()
    config["woolworths_cookies"] = cookies
    _save_config(config)


def get_woolworths_cookies() -> Optional[str]:
    """Return Woolworths cookies string or None."""
    config = _load_config()
    return config.get("woolworths_cookies") or None


def has_woolworths_cookies() -> bool:
    return get_woolworths_cookies() is not None
