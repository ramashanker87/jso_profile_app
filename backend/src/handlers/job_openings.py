import json
from src.errors import AppError
from src.handlers.http import raw_body


def handle(runtime, event, method, path):
    service = runtime.job_opening_service()
    parts = path.strip("/").split("/")
    subject = event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]
    body = None
    if method == "POST":
        try:
            body = json.loads(raw_body(event))
        except (ValueError, UnicodeError):
            raise AppError("Invalid JSON body.") from None
    if path == "/job-openings":
        if method == "GET":
            return service.list()
        if method == "POST":
            return service.create(body, subject)
    if len(parts) == 2 and method == "DELETE":
        return service.delete(parts[1])
    if len(parts) == 3 and parts[2] == "upload" and method == "POST":
        return service.begin_upload(parts[1], body, subject)
    if len(parts) == 4:
        if parts[2:] == ["upload", "complete"] and method == "POST":
            return service.finish_upload(parts[1], body, subject)
        if parts[2] == "attachments" and method == "GET":
            return service.document(parts[1], parts[3])
    raise AppError("Not found.", 404, "NOT_FOUND")
