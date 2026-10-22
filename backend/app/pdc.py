"""Read the public municipal portal's DCSC station series.

The portal mirrors DCSC-00043 in its public Supabase table. This is a
read-only source and is deliberately separate from the ANA adapter.
"""
from datetime import timedelta
import math
import os
import threading
import time
import httpx
from .adapters import ProviderError, parsed_time
from .models import now
from .station_reference import OFFICIAL_STATION

BASE = 'https://uizatcahxcyscjbkxnzp.supabase.co/rest/v1/stations_history'
PORTAL = 'https://pdc.presidentegetulio.sc.gov.br/monitoramento'
_lock = threading.Lock()
_cache = {'until': 0.0, 'value': None}


class PDCClient:
    def __init__(self, transport=None):
        self.key = os.getenv('PDC_SUPABASE_ANON_KEY', '')
        self.transport = transport

    @property
    def ready(self):
        return bool(self.key)

    def readings(self):
        if not self.ready:
            raise ProviderError('Fonte pública municipal não configurada')
        try:
            with httpx.Client(timeout=20, transport=self.transport) as http:
                response = http.get(BASE, params={
                    'select': 'sta_code,sta_name,river_level,created_at,sta_timestamp',
                    'sta_code': 'eq.DCSC-00043', 'river_level': 'not.is.null',
                    'order': 'created_at.desc', 'limit': '96',
                }, headers={'apikey': self.key, 'Authorization': f'Bearer {self.key}'})
                response.raise_for_status()
                rows = response.json()
        except (httpx.RequestError, httpx.HTTPStatusError, ValueError) as exc:
            raise ProviderError('Falha ao consultar leituras do portal municipal') from exc
        if not isinstance(rows, list):
            raise ProviderError('Resposta inválida do portal municipal')
        readings = []
        seen = set()
        for row in rows:
            try:
                if row['sta_code'] != OFFICIAL_STATION['code']:
                    continue
                published = parsed_time(row['created_at'])
                level_m = float(row['river_level'])
                if not math.isfinite(level_m) or level_m < 0 or level_m > 20:
                    continue
                if published in seen:
                    continue
                seen.add(published)
                readings.append({'observed_at': published.isoformat(),
                    'water_level_cm': round(level_m * 100, 2),
                    'station_timestamp': row.get('sta_timestamp')})
            except (KeyError, TypeError, ValueError):
                continue
        return sorted(readings, key=lambda r: r['observed_at'], reverse=True)


def live_station(client=None):
    with _lock:
        if client is None and _cache['value'] is not None and time.monotonic() < _cache['until']:
            return _cache['value']
        readings = (client or PDCClient()).readings()
        latest = readings[0] if readings else None
        age = (now() - parsed_time(latest['observed_at'])) if latest else None
        status = ('ATUALIZADO' if age is not None and -timedelta(minutes=5) <= age <= timedelta(minutes=30)
            else 'ATRASADO' if latest else 'INDISPONIVEL')
        result = {'station': OFFICIAL_STATION, 'portal_url': PORTAL,
            'provider': 'Portal municipal / DCSC', 'status': status,
            'latest': latest, 'items': readings[:48], 'checked_at': now().isoformat()}
        if client is None:
            _cache.update(value=result, until=time.monotonic() + 60)
        return result
