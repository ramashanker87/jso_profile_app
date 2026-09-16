"""Local, explicitly unauthenticated-to-AWS adapter. Bind only to loopback."""

import json
import os
from pathlib import Path
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))
from src.config import Settings
from src.runtime import Runtime
from src.handlers.api import handle
from src.handlers.worker import handle as work
from src.repositories.profile_repository import MemoryProfileRepository
from src.repositories.job_repository import MemoryJobRepository
from src.repositories.job_opening_repository import MemoryJobOpeningRepository
from src.services.storage_service import LocalStorageService, SafeDownloader
from src.services.secrets_service import SecretsService


def main():
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    settings = replace(
        Settings.from_env(),
        local=True,
        cognito_client_id="local-client",
        required_group="",
        attachment_hosts=("127.0.0.1", "localhost"),
        neeto_base_url="http://127.0.0.1:8001/api/external/v1",
        form_id="sample-form",
    )
    os.environ["NEETO_API_KEY"] = "local-demo-key"
    os.environ["NEETO_WEBHOOK_SECRET"] = (
        os.getenv("NEETO_WEBHOOK_SECRET") or "local-webhook-secret"
    )
    executor = ThreadPoolExecutor(max_workers=1)
    storage = LocalStorageService(
        Path(".build/local-documents"),
        SafeDownloader(settings.attachment_hosts, settings.max_file_bytes, local=True),
    )
    runtime = Runtime(
        settings,
        MemoryProfileRepository(),
        MemoryJobRepository(),
        storage,
        SecretsService(local=True),
        lambda event: executor.submit(work, event, None, runtime),
        job_openings=MemoryJobOpeningRepository(),
    )

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_OPTIONS(self):
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "http://localhost:5173")
            self.send_header(
                "Access-Control-Allow-Headers",
                "Authorization,Content-Type,x-neeto-webhook-signature",
            )
            self.send_header("Access-Control-Allow-Methods", "GET,POST,DELETE,OPTIONS")
            self.end_headers()

        def do_GET(self):
            self.route()

        def do_POST(self):
            self.route()

        def do_DELETE(self):
            self.route()

        def route(self):
            parsed = urlparse(self.path)
            if parsed.path.startswith("/local-documents/"):
                from uuid import UUID

                try:
                    name = parsed.path.rsplit("/", 1)[-1]
                    UUID(name.removesuffix(".pdf").removesuffix(".jpg"))
                    body = (storage.root / name).read_bytes()
                except (ValueError, FileNotFoundError):
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg" if name.endswith(".jpg") else "application/pdf")
                self.end_headers()
                self.wfile.write(body)
                return
            length = int(self.headers.get("Content-Length", "0"))
            if length > 200 * 1024:
                self.send_error(413)
                return
            event = {
                "rawPath": parsed.path,
                "queryStringParameters": {
                    k: v[-1] for k, v in parse_qs(parsed.query).items()
                },
                "headers": dict(self.headers),
                "body": self.rfile.read(length).decode(),
                "requestContext": {"http": {"method": self.command}},
            }
            if self.headers.get("Authorization") == "Bearer local-dev-token":
                event["requestContext"]["authorizer"] = {
                    "jwt": {
                        "claims": {
                            "sub": "local-user",
                            "token_use": "access",
                            "client_id": "local-client",
                        }
                    }
                }
            result = handle(event, runtime)
            self.send_response(result["statusCode"])
            for key, value in result["headers"].items():
                self.send_header(key, value)
            self.send_header("Access-Control-Allow-Origin", "http://localhost:5173")
            self.end_headers()
            self.wfile.write(result["body"].encode())

    print("Local API: http://127.0.0.1:8000 (Bearer local-dev-token; no AWS access)")
    try:
        ThreadingHTTPServer(("127.0.0.1", 8000), Handler).serve_forever()
    finally:
        executor.shutdown(wait=False)


if __name__ == "__main__":
    main()
