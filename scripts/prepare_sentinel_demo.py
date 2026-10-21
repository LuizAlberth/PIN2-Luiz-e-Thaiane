"""Fetch the presentation pair using the OAuth credentials in the root .env."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app.satellite_demo import prepare_pair

if __name__ == '__main__':
    pair = prepare_pair()
    for role, (candidate, _) in pair.items():
        print(role, candidate['id'], candidate['acquired_at'].isoformat())
    print('Par real salvo e validado; demonstração disponível sem conexão externa.')
