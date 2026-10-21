"""Load local configuration before API, worker or database imports."""
import os
from pathlib import Path

_env = Path(__file__).resolve().parents[2] / '.env'
if _env.is_file():
    for _line in _env.read_text().splitlines():
        _key, _sep, _value = _line.partition('=')
        if _sep and _key.strip() and not _key.lstrip().startswith('#'):
            os.environ.setdefault(_key.strip(), _value.strip().strip('\"').strip("'"))
