import json
import logging
import signal
import time
from .db import initialize, SessionLocal
from .models import now
from .service import active_config, enqueue_collection, work_once
from .recent_satellite import refresh_latest
from .adapters import CDSEClient, ProviderError

class JSONFormatter(logging.Formatter):
    def format(self, record):
        payload = {'time': now().isoformat(), 'level': record.levelname,
            'component': record.name, 'operation': record.getMessage(),
            'job': getattr(record, 'job', None),
            'correlation_id': getattr(record, 'correlation', None),
            'error': getattr(record, 'error', None) or (str(record.exc_info[1])[:500] if record.exc_info else None)}
        return json.dumps(payload, ensure_ascii=False)

handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
logging.getLogger('httpx').setLevel(logging.WARNING)
stop = False

def stop_worker(*_):
    global stop
    stop = True

def main():
    initialize()
    signal.signal(signal.SIGTERM, stop_worker)
    signal.signal(signal.SIGINT, stop_worker)
    next_satellite_check = 0.0
    while not stop:
        try:
            if time.monotonic() >= next_satellite_check and CDSEClient().ready:
                next_satellite_check = time.monotonic() + 6 * 3600
                try:
                    pair = refresh_latest()
                    logging.info('sentinel_pair_checked %s %s', *(s['acquired_at'] for s in pair['scenes']))
                except ProviderError as exc:
                    next_satellite_check = time.monotonic() + 3600
                    logging.warning('sentinel_pair_unavailable %s', exc)
            with SessionLocal() as db:
                config = active_config(db)
                if config and config.source_mode in ('ANA', 'DCSC'):
                    enqueue_collection(db, config)
                did_work = work_once(db)
            if not did_work:
                time.sleep(3)
        except Exception as exc:
            next_satellite_check = time.monotonic() + 3600
            logging.exception('worker_loop_error')
            time.sleep(5)

if __name__ == '__main__':
    main()
