import json
import os
from typing import Any

from src.errors import AppError


class SecretsService:
    def __init__(self, client: Any = None, arn: str = "", local: bool = False):
        self.client, self.arn, self.local = client, arn, local

    def get(self) -> dict[str, str]:
        if self.local:
            return {
                key: os.getenv(key, "")
                for key in ("NEETO_API_KEY", "NEETO_WEBHOOK_SECRET", "GOOGLE_SERVICE_ACCOUNT_JSON")
            }
        if not self.arn:
            raise AppError(
                "Server integration is not configured.", 503, "NOT_CONFIGURED"
            )
        try:
            value = json.loads(
                self.client.get_secret_value(SecretId=self.arn)["SecretString"]
            )
            return {
                key: str(value.get(key, ""))
                for key in ("NEETO_API_KEY", "NEETO_WEBHOOK_SECRET", "GOOGLE_SERVICE_ACCOUNT_JSON")
            }
        except Exception:
            raise AppError(
                "Server integration secret is unavailable.", 503, "SECRET_UNAVAILABLE"
            ) from None
