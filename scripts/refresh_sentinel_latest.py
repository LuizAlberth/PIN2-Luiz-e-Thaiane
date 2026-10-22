"""Refresh the latest clear Sentinel-2 pair outside the running worker."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app.recent_satellite import refresh_latest

if __name__ == '__main__':
    result = refresh_latest()
    for scene in result['scenes']:
        print(scene['acquired_at'], f"{scene['cloud_percent']}% nuvens no recorte")
