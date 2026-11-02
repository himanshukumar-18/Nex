"""NEX CLI — Secure Credential Storage.

Integrates with OS Keyring (macOS Keychain, Linux Secret Service, Windows Credential Manager)
with a fallback to encrypted/permission-restricted file store (0600) for headless environments.
"""

import json
import logging
import os
import stat
from pathlib import Path
from typing import Any, cast

logger = logging.getLogger(__name__)

KEYRING_SERVICE_NAME = "nex-cli"
TOKEN_KEY = "access_token"
USER_KEY = "user_info"

FALLBACK_DIR = Path.home() / ".nex"
FALLBACK_FILE = FALLBACK_DIR / "credentials.json"


def _has_keyring_backend() -> bool:
    """Detect if a functional OS keyring backend is available."""
    try:
        import keyring
        from keyring.backends.fail import Keyring as FailKeyring

        current = keyring.get_keyring()
        return not isinstance(current, FailKeyring)
    except Exception:
        return False


def _read_fallback_file() -> dict[str, Any]:
    """Read credentials from the secure 0600 fallback file."""
    if not FALLBACK_FILE.exists():
        return {}
    try:
        content = FALLBACK_FILE.read_text(encoding="utf-8")
        return cast(dict[str, Any], json.loads(content))
    except Exception as exc:
        logger.warning("Could not read fallback credentials: %s", str(exc))
        return {}


def _write_fallback_file(data: dict[str, Any]) -> None:
    """Write credentials to fallback file ensuring 0600 permissions."""
    FALLBACK_DIR.mkdir(parents=True, exist_ok=True)
    # Ensure directory is 0700
    try:
        os.chmod(FALLBACK_DIR, stat.S_IRWXU)
    except OSError:
        pass

    content = json.dumps(data, indent=2)
    FALLBACK_FILE.write_text(content, encoding="utf-8")
    try:
        os.chmod(FALLBACK_FILE, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def save_credentials(
    access_token: str,
    user_info: dict[str, Any] | None = None,
) -> None:
    """Store active CLI session token and user identity securely."""
    stored = False
    if _has_keyring_backend():
        try:
            import keyring

            keyring.set_password(KEYRING_SERVICE_NAME, TOKEN_KEY, access_token)
            if user_info:
                keyring.set_password(
                    KEYRING_SERVICE_NAME, USER_KEY, json.dumps(user_info)
                )
            stored = True
        except Exception as exc:
            logger.info(
                "OS keyring store failed, falling back to file store: %s", str(exc)
            )

    if not stored:
        data = _read_fallback_file()
        data[TOKEN_KEY] = access_token
        if user_info:
            data[USER_KEY] = user_info
        _write_fallback_file(data)


def get_stored_token() -> str | None:
    """Retrieve the active CLI access token."""
    # First check environment variable override (standard for CI/headless)
    env_token = os.environ.get("NEX_API_KEY") or os.environ.get("NEX_CLI_TOKEN")
    if env_token:
        return env_token.strip()

    if _has_keyring_backend():
        try:
            import keyring

            token = keyring.get_password(KEYRING_SERVICE_NAME, TOKEN_KEY)
            if token:
                return token
        except Exception:
            pass

    data = _read_fallback_file()
    return data.get(TOKEN_KEY)


def get_stored_user() -> dict[str, Any] | None:
    """Retrieve cached user profile if present."""
    if _has_keyring_backend():
        try:
            import keyring

            raw_user = keyring.get_password(KEYRING_SERVICE_NAME, USER_KEY)
            if raw_user:
                return cast(dict[str, Any], json.loads(raw_user))
        except Exception:
            pass

    data = _read_fallback_file()
    return data.get(USER_KEY)


def clear_credentials() -> None:
    """Delete stored credentials from both Keyring and fallback store."""
    if _has_keyring_backend():
        try:
            import keyring

            try:
                keyring.delete_password(KEYRING_SERVICE_NAME, TOKEN_KEY)
            except Exception:
                pass
            try:
                keyring.delete_password(KEYRING_SERVICE_NAME, USER_KEY)
            except Exception:
                pass
        except Exception:
            pass

    if FALLBACK_FILE.exists():
        try:
            FALLBACK_FILE.unlink()
        except OSError:
            pass
