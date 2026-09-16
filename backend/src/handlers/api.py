import base64
import json
from typing import Any
from src.errors import AppError
from src.handlers import document, neeto_webhook, profile, profiles, sync
from src.handlers.http import response
from src.logging_utils import audit
from src.runtime import aws_runtime


def authorize(event: dict[str, Any], runtime: Any) -> None:
    # API Gateway validates the JWT signature, issuer, audience and expiry. Lambda
    # additionally enforces access-token use. No public Lambda URL is provisioned.
    claims = (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("jwt", {})
        .get("claims", {})
    )
    if not claims.get("sub") or claims.get("token_use") != "access":
        raise AppError(
            "Your session has expired. Please login again.", 401, "UNAUTHENTICATED"
        )
    if (
        not runtime.settings.cognito_client_id
        or claims.get("client_id") != runtime.settings.cognito_client_id
    ):
        raise AppError("Unauthorized client.", 403, "FORBIDDEN")
    group = runtime.settings.required_group
    if group:
        groups = claims.get("cognito:groups", [])
        if isinstance(groups, str):
            # HTTP API can flatten array claims into a space-delimited string.
            # Group names can themselves contain spaces, so never split that value.
            # Read the original array from the token already verified by Gateway.
            try:
                headers = {k.lower(): v for k, v in event.get("headers", {}).items()}
                token = headers.get("authorization", "").split(" ", 1)[1]
                encoded = token.split(".")[1]
                original = json.loads(
                    base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
                )
                if (
                    original.get("sub") != claims["sub"]
                    or original.get("client_id") != claims["client_id"]
                ):
                    raise ValueError("Claims do not match")
                groups = original.get("cognito:groups", [])
            except (ValueError, IndexError, KeyError, TypeError):
                groups = []
        if not isinstance(groups, list) or group not in groups:
            raise AppError(
                "Your account is not authorized for Profile Library.", 403, "FORBIDDEN"
            )


def handle(event: dict[str, Any], runtime: Any) -> dict[str, Any]:
    try:
        method = event.get("requestContext", {}).get("http", {}).get("method", "")
        path = event.get("rawPath", "").rstrip("/") or "/"
        query = event.get("queryStringParameters") or {}
        if method == "POST" and path == "/webhooks/neetform":
            return response(202, neeto_webhook.handle(runtime, event))
        authorize(event, runtime)
        if path == "/sambhav" or path.startswith("/sambhav/"):
            from src.handlers import sambhav
            return response(200, sambhav.handle(runtime, event, method, path))
        if path == "/members/sync" and method == "POST":
            return response(202, sync.start(runtime, members=True))
        if path == "/members/sync" and method == "GET":
            return response(200, sync.public_job(runtime.member_jobs.latest() if runtime.member_jobs else None))
        if method == "GET" and path.startswith("/members/sync/"):
            job_id = path.removeprefix("/members/sync/")
            job = runtime.member_jobs.get(job_id) if runtime.member_jobs and not job_id.startswith("STATE") else None
            if not job:
                raise AppError("Sync job not found.", 404, "NOT_FOUND")
            return response(200, sync.public_job(job))
        if method == "POST" and path == "/members/detail":
            claims = event["requestContext"]["authorizer"]["jwt"]["claims"]
            user = runtime.cognito.admin_get_user(
                UserPoolId=runtime.settings.cognito_pool_id,
                Username=claims.get("username") or claims["sub"])
            attributes = {a["Name"]: a["Value"] for a in user.get("UserAttributes", [])}
            email = attributes.get("email", "").strip().casefold()
            if (not user.get("Enabled") or attributes.get("sub") != claims["sub"]
                    or attributes.get("email_verified") != "true" or not email
                    or email != query.get("email", "").strip().casefold()):
                raise AppError("You can only edit your own member information using a verified email.", 403, "FORBIDDEN")
            try:
                raw = event.get("body") or ""
                if event.get("isBase64Encoded"):
                    raw = base64.b64decode(raw).decode("utf-8")
                fields = json.loads(raw)
            except (ValueError, UnicodeError):
                raise AppError("Invalid update body.") from None
            return response(200, runtime.member_service().update(email, fields, claims["sub"]))
        if method == "GET" and path == "/members/detail":
            return response(200, runtime.member_service().get(query.get("email", "")))
        if method == "GET" and path == "/members":
            try:
                page, size = int(query.get("page", "1")), int(query.get("pageSize", "25"))
            except ValueError:
                raise AppError("Page and pageSize must be integers.") from None
            return response(200, runtime.member_service().list(query.get("search", ""), page, size, query.get("country", ""), query.get("chapter", ""), query.get("region", "")))
        if method == "GET" and path == "/profiles":
            return response(200, profiles.handle(runtime, query))
        if method == "POST" and path == "/sync":
            return response(202, sync.start(runtime))
        if method == "GET" and path == "/sync":
            return response(200, sync.public_job(runtime.jobs.latest()))
        parts = path.strip("/").split("/")
        if method == "GET" and len(parts) == 2 and parts[0] == "sync":
            job = runtime.jobs.get(parts[1]) if parts[1] != "STATE" else None
            if not job:
                raise AppError("Sync job not found.", 404, "NOT_FOUND")
            return response(200, sync.public_job(job))
        if method == "GET" and len(parts) in (2, 3) and parts[0] == "profiles":
            if len(parts) == 2:
                return response(200, profile.handle(runtime, parts[1]))
            if parts[2] == "document":
                return response(200, document.handle(runtime, parts[1], query))
        raise AppError("Not found.", 404, "NOT_FOUND")
    except AppError as error:
        return response(error.status, {"error": str(error), "code": error.code})
    except Exception as error:
        audit("api_error", status="FAILED", errorType=type(error).__name__)
        return response(
            500,
            {
                "error": "Unable to complete this request. Please try again.",
                "code": "INTERNAL_ERROR",
            },
        )


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    return handle(event, aws_runtime())
