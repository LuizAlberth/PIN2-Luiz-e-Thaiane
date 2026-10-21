"""External data adapters. All third-party credentials stay in the server process."""
from datetime import datetime, timedelta, timezone
from io import BytesIO
import json
import os
import tarfile
import time
from zoneinfo import ZoneInfo
import httpx
from PIL import Image, ImageStat
from shapely.geometry import box, shape

ANA_BASE = 'https://www.ana.gov.br/hidrowebservice/EstacoesTelemetricas'
CDSE_BASE = 'https://sh.dataspace.copernicus.eu'
CDSE_TOKEN = 'https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token'
SAO_PAULO = ZoneInfo('America/Sao_Paulo')

class ProviderError(Exception):
    def __init__(self, message: str, retry_after: int | None = None):
        super().__init__(message)
        self.retry_after = retry_after


def parsed_time(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        result = value
    else:
        result = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    return (result.replace(tzinfo=SAO_PAULO) if result.tzinfo is None else result).astimezone(timezone.utc)


def checked(response: httpx.Response):
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        wait = response.headers.get('Retry-After')
        raise ProviderError(f'HTTP {response.status_code} do provedor', int(wait) if wait and wait.isdigit() else None) from exc
    return response

class ANAClient:
    def __init__(self, transport=None):
        self.identifier = os.getenv('ANA_IDENTIFICADOR', '')
        self.password = os.getenv('ANA_SENHA', '')
        self.http = httpx.Client(timeout=25, transport=transport)
        self._token = ''
        self._expires = 0.0

    @property
    def ready(self):
        return bool(self.identifier and self.password)

    def token(self, refresh=False):
        if not self.ready:
            raise ProviderError('Credenciais ANA não configuradas')
        if self._token and self._expires > time.time() + 120 and not refresh:
            return self._token
        try:
            response = checked(self.http.get(f'{ANA_BASE}/OAUth/v1', headers={
                'Identificador': self.identifier, 'Senha': self.password}))
        except httpx.RequestError as exc:
            raise ProviderError('Falha de conexão com ANA') from exc
        payload = response.json()
        item = payload.get('items') or {}
        if isinstance(item, list):
            item = item[0] if item else {}
        token = item.get('tokenautenticacao') or payload.get('tokenautenticacao')
        if not token:
            raise ProviderError('ANA não retornou tokenautenticacao')
        self._token = token
        self._expires = time.time() + 3600
        return token

    def request(self, path: str, params: dict):
        for retry in (False, True):
            try:
                response = self.http.get(f'{ANA_BASE}/{path}/v1',
                    headers={'Authorization': f'Bearer {self.token(refresh=retry)}'}, params=params)
            except httpx.RequestError as exc:
                raise ProviderError('Falha de conexão com ANA') from exc
            if response.status_code == 401 and not retry:
                continue
            payload = checked(response).json()
            if payload.get('status') not in ('OK', None):
                raise ProviderError(f'ANA retornou: {payload.get("message", "erro")}')
            return payload.get('items') or []
        raise ProviderError('Falha na autenticação ANA')

    def station(self, code: str):
        items = self.request('HidroInventarioEstacoes', {'CodigoDaEstacao': code})
        return next((item for item in items if str(item.get('codigoestacao') or item.get('Codigo_Estacao')
            or item.get('CodigoDaEstacao') or item.get('Codigo')) == str(code)), None)

    def readings(self, code: str, date: datetime | None = None, window='DIAS_2'):
        params = {'CodigoDaEstacao': code, 'TipoFiltroData': 'DATA_LEITURA', 'RangeIntervaloDeBusca': window}
        if date:
            params['DataBusca'] = date.astimezone(SAO_PAULO).strftime('%Y-%m-%d')
        items = self.request('HidroinfoanaSerieTelemetricaAdotada', params)
        result = []
        for item in items:
            raw_level = item.get('Cota_Adotada')
            try:
                level = float(raw_level) if raw_level not in ('', None) else None
            except (ValueError, TypeError):
                level = None
            quality = {'0': 'VALIDA', '1': 'SUSPEITA', '2': 'RUIM'}.get(str(item.get('Cota_Adotada_Status')), 'SEM_COTA')
            if level is None:
                quality = 'SEM_COTA'
            if not item.get('Data_Hora_Medicao'):
                continue
            result.append({'observed_at': parsed_time(item['Data_Hora_Medicao']), 'level_cm': level,
                'quality': quality, 'raw': item})
        return result

# Fixed visualization parameters for comparable GRD imagery.
EVALSCRIPT = '''//VERSION=3
function setup() {
  return {input: ["VV", "dataMask"], mosaicking: Mosaicking.ORBIT,
    output: {id: "default", bands: 4, sampleType: "AUTO"}};
}
function evaluatePixel(samples) {
  let s = samples.find(sample => sample.dataMask === 1);
  if (!s) return [0, 0, 0, 0];
  let v = Math.max(0, Math.min(1, (10 * Math.log10(Math.max(s.VV, 0.00001)) + 27) / 22));
  return [v, v, v, 1];
}
function updateOutputMetadata(scenes, inputMetadata, outputMetadata) {
  outputMetadata.userData = {productIds: scenes.orbits.flatMap(orbit =>
    orbit.tiles.map(tile => tile.sentinel1ProductId))};
}'''

class CDSEClient:
    def __init__(self, transport=None):
        self.client_id = os.getenv('CDSE_CLIENT_ID', '')
        self.client_secret = os.getenv('CDSE_CLIENT_SECRET', '')
        self.http = httpx.Client(timeout=60, transport=transport)
        self._token = ''
        self._expires = 0.0

    @property
    def ready(self):
        return bool(self.client_id and self.client_secret)

    def headers(self):
        if not self.ready:
            raise ProviderError('Credenciais Copernicus não configuradas')
        if time.time() + 120 > self._expires:
            try:
                response = checked(self.http.post(CDSE_TOKEN, data={'grant_type': 'client_credentials',
                    'client_id': self.client_id, 'client_secret': self.client_secret}))
            except httpx.RequestError as exc:
                raise ProviderError('Falha de conexão com Copernicus') from exc
            data = response.json()
            self._token = data['access_token']
            self._expires = time.time() + int(data.get('expires_in', 600))
        return {'Authorization': f'Bearer {self._token}'}

    def search(self, bbox: list, start: datetime, end: datetime, collection='sentinel-1-grd'):
        body = {'bbox': bbox, 'datetime': f'{start.isoformat()}/{end.isoformat()}',
            'collections': [collection], 'limit': 100}
        features = []
        for _ in range(5):
            try:
                data = checked(self.http.post(f'{CDSE_BASE}/catalog/v1/search', json=body, headers=self.headers())).json()
            except httpx.RequestError as exc:
                raise ProviderError('Falha de conexão com catálogo Copernicus') from exc
            features.extend(data.get('features', []))
            next_page = data.get('context', {}).get('next')
            if next_page is None:
                break
            body['next'] = next_page
        return features

    @staticmethod
    def properties(feature):
        p = feature.get('properties') or {}
        return {'id': feature['id'], 'acquired_at': parsed_time(p['datetime']),
            'instrument_mode': str(p.get('sar:instrument_mode') or '').upper(),
            'orbit_direction': str(p.get('sat:orbit_state') or '').upper(),
            'relative_orbit': p.get('sat:relative_orbit'),
            'polarization': str(p.get('s1:polarization') or '').upper(), 'raw': feature}

    @staticmethod
    def compatible(candidate, baseline):
        return (candidate['instrument_mode'] == baseline['instrument_mode'] and
            candidate['orbit_direction'] == baseline['orbit_direction'] and
            candidate['polarization'] == baseline['polarization'] and
            candidate['relative_orbit'] == baseline['relative_orbit'])

    def select(self, features, role, trigger: datetime, baseline=None, bbox=None):
        candidates = []
        for item in features:
            try:
                p = self.properties(item)
                if p['instrument_mode'] != 'IW' or p['polarization'] not in ('DV', 'VV') or not p['orbit_direction'] or p['relative_orbit'] is None:
                    continue
                if bbox:
                    if not item.get('geometry'):
                        continue
                    target = box(*bbox)
                    coverage = shape(item['geometry']).intersection(target).area / target.area
                    if coverage < .99:
                        continue
                    p['coverage_percent'] = round(coverage * 100, 1)
                if baseline and not self.compatible(p, baseline):
                    continue
                candidates.append(p)
            except (KeyError, ValueError, TypeError):
                continue
        candidates.sort(key=lambda x: x['acquired_at'], reverse=role == 'BASELINE')
        return candidates[0] if candidates else None

    def process(self, bbox: list, candidate: dict):
        instant = candidate['acquired_at']
        polarization = candidate['polarization']
        payload = {
            'input': {'bounds': {'bbox': bbox, 'properties': {'crs': 'http://www.opengis.net/def/crs/EPSG/0/4326'}},
                'data': [{'type': 'sentinel-1-grd',
                    'dataFilter': {'timeRange': {'from': instant.isoformat(), 'to': (instant + timedelta(seconds=1)).isoformat()},
                        'acquisitionMode': candidate['instrument_mode'], 'polarization': polarization,
                        'orbitDirection': candidate['orbit_direction']},
                    'processing': {'backCoeff': 'SIGMA0_ELLIPSOID', 'orthorectify': True}}]},
            'output': {'width': 512, 'height': 512,
                'responses': [{'identifier': 'default', 'format': {'type': 'image/png'}},
                    {'identifier': 'userdata', 'format': {'type': 'application/json'}}]},
            'evalscript': EVALSCRIPT}
        try:
            response = checked(self.http.post(f'{CDSE_BASE}/api/v1/process', json=payload,
                headers={**self.headers(), 'Accept': 'application/x-tar'}))
        except httpx.RequestError as exc:
            raise ProviderError('Falha de conexão com Process API') from exc
        try:
            with tarfile.open(fileobj=BytesIO(response.content), mode='r:*') as archive:
                image = archive.extractfile('default.png').read()
                metadata = json.load(archive.extractfile('userdata.json'))
            products = metadata['productIds']
            if not products or set(products) != {candidate['id']}:
                raise ProviderError('O produto processado não corresponde à cena escolhida no catálogo')
        except (tarfile.TarError, OSError, KeyError, AttributeError, ValueError, TypeError) as exc:
            raise ProviderError('Resposta de imagem ou proveniência incompleta no Copernicus') from exc
        verify_png(image)
        return image


def verify_png(data):
    try:
        with Image.open(BytesIO(data)) as image:
            image.verify()
        with Image.open(BytesIO(data)) as image:
            if image.format != 'PNG':
                raise ValueError('Formato inválido')
            if image.size[0] <= 0 or image.size[1] <= 0:
                raise ValueError('Tamanho inválido')
            if image.getbbox() is None:
                raise ValueError('Imagem sem pixels válidos')
            if image.mode in ('RGBA', 'LA') and image.getchannel('A').getextrema() == (0, 0):
                raise ValueError('Imagem sem pixels válidos')
            if image.mode in ('RGBA', 'LA'):
                alpha = image.getchannel('A').histogram()
                if sum(alpha[:250]) / (image.width * image.height) > .01:
                    raise ValueError('Cobertura insuficiente na área')
            sample = image.convert('RGB').resize((128, 128))
            if max(ImageStat.Stat(sample).stddev) < 5:
                raise ValueError('Imagem sem contraste útil')
            pixels = list(sample.getdata())
            if sum(min(p) > 240 for p in pixels) / len(pixels) > .95:
                raise ValueError('Imagem quase toda branca')
            return image.size
    except Exception as exc:
        raise ProviderError('Imagem inválida ou incompleta') from exc
