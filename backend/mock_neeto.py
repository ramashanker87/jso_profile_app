"""Local Neeto API fixture with pagination and a real fictional PDF."""

import json
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/files/sample.pdf":
            data = (
                Path(__file__).parent / "tests/fixtures/sample-profile.pdf"
            ).read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if parsed.path != "/api/external/v1/forms/sample-form/submissions":
            self.send_error(404)
            return
        if self.headers.get("X-Api-Key") != "local-demo-key":
            self.send_error(401)
            return
        query = parse_qs(parsed.query)
        try:
            page = max(1, int(query.get("page_number", ["1"])[0]))
            size = max(1, min(100, int(query.get("page_size", ["20"])[0])))
        except ValueError:
            self.send_error(400)
            return
        rows = json.loads(
            (Path(__file__).parent / "tests/fixtures/sample_profiles.json").read_text()
        )
        submissions = [
            {
                "id": p["submissionId"],
                "created_at": p["submissionDate"],
                "responses": [
                    {"label": label, "value": p[key]}
                    for label, key in [
                        ("Name", "name"),
                        ("Email", "email"),
                        ("LinkedIn", "linkedinUrl"),
                        ("Support", "supportRaw"),
                        ("Theme", "theme"),
                    ]
                ],
            }
            for p in rows
        ]
        for entry in submissions:
            entry["responses"].append(
                {
                    "label": "File upload",
                    "value": {
                        "name": "profile.pdf",
                        "url": "http://127.0.0.1:8001/files/sample.pdf",
                    },
                }
            )
        data = json.dumps(
            {
                "submissions": submissions[(page - 1) * size : page * size],
                "total_count": len(rows),
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    print("Mock Neeto: http://127.0.0.1:8001")
    ThreadingHTTPServer(("127.0.0.1", 8001), Handler).serve_forever()
