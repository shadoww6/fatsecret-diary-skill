"""Credentials and paths. Everything secret lives in `.env` (or real environment variables).

Credentials can also be given as one "connection string" CONSUMER_KEY:CONSUMER_SECRET[:ACCESS_TOKEN:ACCESS_SECRET]
via the FATSECRET_CONNECTION variable or `fatsecret connect` — handy for AI-assistant sandboxes."""

from __future__ import annotations

import json
import os
from pathlib import Path

from .client import FatSecretClient


def _home() -> Path:
    if os.environ.get("FATSECRET_HOME"):
        return Path(os.environ["FATSECRET_HOME"])
    checkout = Path(__file__).resolve().parent.parent
    if (checkout / "pyproject.toml").exists():  # running from a cloned repo
        return checkout
    return Path.home() / ".fatsecret"


ROOT = _home()
ENV_FILE = ROOT / ".env"
PENDING_AUTH_FILE = ROOT / ".fatsecret_pending_auth.json"
DATA_DIR = Path(os.environ.get("FATSECRET_DATA_DIR") or ROOT / "data")

KEY_VARS = ("FATSECRET_CONSUMER_KEY", "FATSECRET_CONSUMER_SECRET")
TOKEN_VARS = ("FATSECRET_ACCESS_TOKEN", "FATSECRET_ACCESS_SECRET")
ALL_VARS = KEY_VARS + TOKEN_VARS


class ConfigError(Exception):
    pass


def parse_connection(s):
    parts = [p.strip() for p in (s or "").strip().strip('"').split(":")]
    if len(parts) not in (2, 4) or not all(parts):
        raise ConfigError("connection string must look like KEY:SECRET or KEY:SECRET:TOKEN:TOKEN_SECRET")
    return dict(zip(ALL_VARS, parts))


def connection_string():
    values = [get(v) for v in ALL_VARS]
    return ":".join(values) if all(values) else None


def _read_env_file():
    values = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                values[k.strip()] = v.strip().strip('"').strip("'")
    return values


def get(name):
    """Real environment variables win over .env (handy for Codespaces / CI secrets)."""
    if os.environ.get(name):
        return os.environ[name]
    if os.environ.get("FATSECRET_CONNECTION"):
        value = parse_connection(os.environ["FATSECRET_CONNECTION"]).get(name)
        if value:
            return value
    return _read_env_file().get(name) or None


def save_env(updates: dict):
    """Update or append KEY=value lines in .env, keeping everything else intact."""
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    pending = dict(updates)
    for i, line in enumerate(lines):
        key = line.split("=", 1)[0].strip()
        if "=" in line and key in pending:
            lines[i] = f"{key}={pending.pop(key)}"
    lines += [f"{k}={v}" for k, v in pending.items()]
    ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def make_client(authorized=True) -> FatSecretClient:
    key, secret = (get(v) for v in KEY_VARS)
    if not key or not secret:
        raise ConfigError(
            "No API keys. Run `fatsecret connect KEY:SECRET` "
            f"or put FATSECRET_CONSUMER_KEY and FATSECRET_CONSUMER_SECRET into {ENV_FILE}."
        )
    if not authorized:
        return FatSecretClient(key, secret)
    token, token_secret = (get(v) for v in TOKEN_VARS)
    if not token or not token_secret:
        raise ConfigError("FatSecret account is not connected yet: run `fatsecret auth`.")
    return FatSecretClient(key, secret, token, token_secret)


def save_pending_auth(token, token_secret):
    PENDING_AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
    PENDING_AUTH_FILE.write_text(json.dumps({"token": token, "secret": token_secret}), encoding="utf-8")


def pop_pending_auth():
    if not PENDING_AUTH_FILE.exists():
        raise ConfigError("No authorization in progress: run `fatsecret auth --no-wait` first.")
    data = json.loads(PENDING_AUTH_FILE.read_text(encoding="utf-8"))
    PENDING_AUTH_FILE.unlink()
    return data["token"], data["secret"]
