"""Start API, worker and frontend together. Ctrl+C stops all three."""
from pathlib import Path
import os
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
import app  # Loads .env without overriding shell variables.

def main():
    env = os.environ.copy()
    api_port = int(env.get('PIN2_API_PORT', '8000'))
    web_port = int(env.get('PIN2_WEB_PORT', '5173'))
    env.setdefault('DATABASE_URL', f'sqlite:///{ROOT / "pin2.db"}')
    env.setdefault('LOCAL_STORAGE', str(ROOT / 'storage'))
    env['API_PROXY_TARGET'] = f'http://127.0.0.1:{api_port}'
    commands = [
        ([sys.executable, '-m', 'uvicorn', 'app.api:app', '--host', '127.0.0.1', '--port', str(api_port)], ROOT / 'backend'),
        ([sys.executable, '-m', 'app.worker'], ROOT / 'backend'),
        (['npm', 'run', 'dev', '--', '--host', '127.0.0.1', '--port', str(web_port), '--strictPort'], ROOT / 'frontend'),
    ]
    processes = []
    def stop(*_):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)
    try:
        for command, cwd in commands:
            processes.append(subprocess.Popen(command, cwd=cwd, env=env, start_new_session=True))
        print(f'Aplicação: http://localhost:{web_port} · Admin: credenciais do .env', flush=True)
        while True:
            if any(p.poll() is not None for p in processes):
                raise RuntimeError(f'Um serviço encerrou. Confira a saída acima e se as portas {api_port}/{web_port} estão livres.')
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        for process in processes:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
        for process in processes:
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()

if __name__ == '__main__':
    main()
