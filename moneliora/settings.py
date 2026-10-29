"""Application settings; no secrets are exposed in the public catalog."""
from dataclasses import dataclass, field
from pathlib import Path
import os
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]

@dataclass(frozen=True)
class Settings:
    database: Path = field(default_factory=lambda: Path(os.getenv('MONELIORA_DB', str(ROOT / 'data/moneliora.db'))))
    admin_token: str = field(default_factory=lambda: os.getenv('MONELIORA_ADMIN_TOKEN', ''))
    origin: str = field(default_factory=lambda: os.getenv('MONELIORA_ORIGIN', 'http://127.0.0.1:8000').rstrip('/'))
    public_preview: bool = field(default_factory=lambda: os.getenv('MONELIORA_PUBLIC_PREVIEW', 'false').lower() == 'true')
    pilot_only: bool = field(default_factory=lambda: os.getenv('MONELIORA_PILOT_ONLY', 'false').lower() == 'true')
    pilot_enabled: bool = field(default_factory=lambda: os.getenv('MONELIORA_PILOT_ENABLED', 'false').lower() == 'true')
    seller_name: str = field(default_factory=lambda: os.getenv('MONELIORA_SELLER_NAME', '').strip())
    privacy_url: str = field(default_factory=lambda: os.getenv('MONELIORA_PRIVACY_URL', '').strip())
    terms_url: str = field(default_factory=lambda: os.getenv('MONELIORA_TERMS_URL', '').strip())
    legal_url: str = field(default_factory=lambda: os.getenv('MONELIORA_LEGAL_URL', '').strip())

    @property
    def pilot_available(self):
        urls = (self.privacy_url, self.terms_url, self.legal_url)
        return bool(self.pilot_enabled and not self.public_preview and self.seller_name
                    and len(self.admin_token) >= 32 and urlsplit(self.origin).scheme == 'https'
                    and all(safe_https_url(url) for url in urls))


def safe_https_url(value):
    try:
        parsed = urlsplit(value)
        return (parsed.scheme == 'https' and bool(parsed.hostname) and not parsed.username
                and not parsed.password and not any(c.isspace() for c in value))
    except ValueError:
        return False
