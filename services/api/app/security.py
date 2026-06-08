import hashlib
import hmac


def verify_github_signature(body: bytes, signature_header: str | None, secret: str | None) -> bool:
    """Verify GitHub X-Hub-Signature-256.

    If secret is not configured, verification is skipped intentionally for local dev.
    """
    if not secret:
        return True
    if not signature_header:
        return False
    prefix = "sha256="
    if not signature_header.startswith(prefix):
        return False
    expected = prefix + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)
