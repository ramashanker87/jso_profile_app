import json
import logging

logger = logging.getLogger("profile_library")
logger.setLevel(logging.INFO)


def audit(event: str, **fields: str) -> None:
    allowed = {"submissionId", "profileId", "operation", "status", "errorType", "jobId"}
    logger.info(
        json.dumps(
            {"event": event, **{k: v for k, v in fields.items() if k in allowed}},
            ensure_ascii=True,
        )
    )
