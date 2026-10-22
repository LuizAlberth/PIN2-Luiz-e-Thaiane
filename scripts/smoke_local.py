"""Run the real HTTP demo flow with API, worker and Vite, without external accounts.

Requires the Python and npm dependencies described in README.md. Uses temporary
SQLite and image directories, and stops every child process on exit.
"""
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
WEB_PORT = os.getenv('SMOKE_WEB_PORT', '5173')
API_PORT = os.getenv('SMOKE_API_PORT', '8000')
API = f"http://127.0.0.1:{WEB_PORT}"


def request(path, *, body=None, token=None):
    payload = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if payload is not None else {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with urlopen(Request(API + path, data=payload, headers=headers), timeout=10) as response:
        data = response.read()
        return response.status, response.headers, data


def json_request(path, *, body=None, token=None):
    status, _, data = request(path, body=body, token=token)
    return status, json.loads(data)


def wait_for(predicate, processes, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for name, process in processes:
            if process.poll() is not None:
                raise RuntimeError(f"{name} parou com código {process.returncode}")
        try:
            result = predicate()
            if result:
                return result
        except (URLError, HTTPError, ValueError, KeyError):
            pass
        time.sleep(0.5)
    raise TimeoutError("Fluxo HTTP não concluiu no prazo")


def main():
    python = ROOT / ".venv/bin/python"
    if not python.exists() or not (ROOT / "frontend/node_modules").exists():
        raise RuntimeError("Instale as dependências conforme o README antes do smoke test")
    with tempfile.TemporaryDirectory(prefix="pin2-smoke-") as temp:
        temp = Path(temp)
        env = os.environ.copy()
        env.update(DATABASE_URL=f"sqlite:///{temp / 'pin2.db'}", LOCAL_STORAGE=str(temp / "images"),
                   ADMIN_EMAIL="smoke@example.com", ADMIN_PASSWORD="senha-local-de-teste-123",
                   APP_SECRET="segredo-local-de-teste-com-mais-de-32-caracteres")
        env['API_PROXY_TARGET'] = f'http://127.0.0.1:{API_PORT}'
        for key in ("POSTGRES_HOST", "S3_ENDPOINT", "ANA_IDENTIFICADOR", "ANA_SENHA",
                    "CDSE_CLIENT_ID", "CDSE_CLIENT_SECRET"):
            env[key] = ''
        commands = [
            ("api", [str(python), "-m", "uvicorn", "app.api:app", "--host", "127.0.0.1", "--port", API_PORT], ROOT / "backend"),
            ("worker", [str(python), "-m", "app.worker"], ROOT / "backend"),
            ("web", ["npm", "run", "dev", "--", "--host", "127.0.0.1", "--port", WEB_PORT, "--strictPort"], ROOT / "frontend"),
        ]
        processes = []
        logs = []
        try:
            for name, command, cwd in commands:
                logfile = (temp / f"{name}.log").open("w+")
                logs.append((name, logfile))
                processes.append((name, subprocess.Popen(command, cwd=cwd, env=env,
                    stdout=logfile, stderr=subprocess.STDOUT, start_new_session=True)))
            wait_for(lambda: json_request("/api/health")[1].get("status") == "ok", processes)
            status, _, docs = request("/api/docs")
            assert status == 200 and b"Swagger UI" in docs
            status, schema = json_request("/api/openapi.json")
            assert status == 200 and "/api/events" in schema["paths"]
            status, _, html = request("/")
            assert status == 200 and b'<div id="root"></div>' in html
            status, _, javascript = request("/src/main.jsx")
            assert status == 200 and b"createRoot" in javascript

            status, login = json_request("/api/auth/admin", body={"password": env["ADMIN_PASSWORD"]})
            assert status == 200 and login["token"]
            token = login["token"]
            status, created = json_request("/api/admin/demo", body={}, token=token)
            assert status == 200 and created["config"]["source_mode"] == "DEMO"
            event_id = created["replay"]["events_created"][0]
            event = wait_for(lambda: (lambda response: response if response["status"] == "DISPONIVEL" else None)(
                json_request(f"/api/events/{event_id}", token=token)[1]), processes)
            assert event["mode"] == "SIMULACAO"
            status, public = json_request("/api/events?mode=SIMULACAO")
            assert status == 200 and any(item["id"] == event_id for item in public["items"])
            status, detail = json_request(f"/api/events/{event_id}")
            assert status == 200 and all(detail["scenes"][role]["source"] == "CDSE"
                for role in ("BASELINE", "POST_EVENT"))
            for role in ("BASELINE", "POST_EVENT"):
                status, headers, png = request(f"/api/events/{event_id}/scene/{role}")
                assert status == 200 and headers.get_content_type() == "image/png" and png[:8] == b"\x89PNG\r\n\x1a\n"
            status, reprocessed = json_request(f"/api/admin/events/{event_id}/reprocess", body={}, token=token)
            assert status == 200 and reprocessed["version"] == 2
            wait_for(lambda: all(scene and scene["version"] == 2 for scene in
                json_request(f"/api/events/{event_id}")[1]["scenes"].values()), processes)
            print("OK: interface Vite, API/docs, login, demonstração, worker, PNG público e reprocessamento v2")
        except Exception:
            for name, logfile in logs:
                logfile.flush()
                logfile.seek(0)
                print(f"--- {name} ---\n{logfile.read()[-3000:]}")
            raise
        finally:
            for _, process in processes:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGTERM)
            for _, process in processes:
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
            for _, logfile in logs:
                logfile.close()


if __name__ == "__main__":
    main()
