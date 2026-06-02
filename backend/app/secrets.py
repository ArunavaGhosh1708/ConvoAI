"""
GCP Secret Manager client with environment variable fallback.

In production (GCP_PROJECT_ID set), secrets are fetched from Secret Manager.
In development / CI, environment variables serve as the source of truth.

Usage:
    from app.secrets import get_secret
    api_key = get_secret("OPENAI_API_KEY")
"""

import logging
import os

logger = logging.getLogger(__name__)

_GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "")
_SECRET_VERSION  = os.getenv("GCP_SECRET_VERSION", "latest")

# Module-level client cache
_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client
    try:
        from google.cloud import secretmanager
        _client = secretmanager.SecretManagerServiceClient()
        return _client
    except ImportError:
        raise ImportError(
            "google-cloud-secret-manager is required for GCP Secret Manager. "
            "Install it: pip install google-cloud-secret-manager"
        )


def get_secret(name: str, default: str | None = None) -> str:
    """
    Fetch a secret value.

    Priority:
      1. GCP Secret Manager  (when GCP_PROJECT_ID is set)
      2. Environment variable (same name)
      3. `default` argument
    """
    if _GCP_PROJECT_ID:
        try:
            client = _get_client()
            secret_path = f"projects/{_GCP_PROJECT_ID}/secrets/{name}/versions/{_SECRET_VERSION}"
            response = client.access_secret_version(request={"name": secret_path})
            value = response.payload.data.decode("UTF-8").strip()
            logger.debug("Loaded secret '%s' from GCP Secret Manager", name)
            return value
        except Exception as exc:
            logger.warning(
                "Failed to load '%s' from Secret Manager: %s — falling back to env var", name, exc
            )

    env_val = os.getenv(name)
    if env_val is not None:
        return env_val

    if default is not None:
        return default

    raise RuntimeError(
        f"Secret '{name}' not found in GCP Secret Manager or environment variables"
    )


def preload_secrets(names: list[str]) -> dict[str, str]:
    """Bulk-fetch secrets at startup and return as a dict."""
    return {name: get_secret(name) for name in names}
