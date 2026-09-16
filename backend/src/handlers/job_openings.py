import json
from src.errors import AppError
from src.handlers.http import raw_body


def handle(runtime, event, method, path):
    service = runtime.job_opening_service()
    if path == "/job-openings" and method == "GET":
        return service.list()
    if path == "/job-openings" and method == "POST":
        try:
            body = json.loads(raw_body(event))
        except (ValueError, UnicodeError):
            raise AppError("Invalid JSON body.") from None
        subject = event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"]
        return service.create(body, subject)
    if method == "DELETE" and path.startswith("/job-openings/"):
        return service.delete(path.removeprefix("/job-openings/"))
    raise AppError("Not found.", 404, "NOT_FOUND")
