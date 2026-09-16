import hashlib
import hmac
import re


def verify_signature(raw_body: bytes, signature: str, secret: str) -> bool:
    if not secret or not re.fullmatch(r"sha256=[a-fA-F0-9]{64}", signature or ""):
        return False
    expected = (
        "sha256=" + hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    )
    return hmac.compare_digest(expected, signature.lower())
