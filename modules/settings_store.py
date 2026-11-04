import os
import tempfile
import threading
from pathlib import Path
from urllib.parse import urlparse

from dotenv import set_key


class SettingsError(ValueError):
    pass


class SettingsStore:
    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.Lock()

    def update(self, values):
        with self.lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path = None
            try:
                with tempfile.NamedTemporaryFile(dir=self.path.parent, prefix='.env.', delete=False) as temporary:
                    temporary_path = Path(temporary.name)
                if self.path.exists():
                    temporary_path.write_bytes(self.path.read_bytes())
                    os.chmod(temporary_path, self.path.stat().st_mode)
                else:
                    os.chmod(temporary_path, 0o600)
                for key, value in values.items():
                    set_key(str(temporary_path), key, str(value))
                os.replace(temporary_path, self.path)
            finally:
                if temporary_path and temporary_path.exists():
                    temporary_path.unlink()


def boolean_value(value, field):
    if not isinstance(value, bool):
        raise SettingsError(f'{field} must be a boolean')
    return str(value).lower()


def text_value(value, field, maximum=500, required=False):
    if not isinstance(value, str):
        raise SettingsError(f'{field} must be text')
    value = value.strip()
    if required and not value:
        raise SettingsError(f'{field} is required')
    if len(value) > maximum or '\n' in value or '\r' in value:
        raise SettingsError(f'{field} is invalid')
    return value


def integer_value(value, field, minimum, maximum):
    if isinstance(value, bool):
        raise SettingsError(f'{field} must be an integer')
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise SettingsError(f'{field} must be an integer') from None
    if parsed < minimum or parsed > maximum:
        raise SettingsError(f'{field} must be between {minimum} and {maximum}')
    return str(parsed)


def url_value(value, field):
    value = text_value(value, field, maximum=2048, required=True)
    parsed = urlparse(value)
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
        raise SettingsError(f'{field} must be an HTTP or HTTPS URL')
    return value
