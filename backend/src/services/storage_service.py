from contextlib import contextmanager
import hashlib
import ipaddress
import os
from pathlib import Path
import re
import socket
import tempfile
import time
from typing import Any, BinaryIO, Iterator, Protocol
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse, quote

import certifi
import urllib3
from botocore.exceptions import ClientError

from src.errors import DocumentError
from src.models.profile import FileInput


def safe_filename(name: str) -> str:
    basename = name.replace("\\", "/").split("/")[-1]
    cleaned = re.sub(r"[^a-zA-Z0-9._ -]", "_", basename).strip(" .")[:120]
    return (
        cleaned if cleaned.lower().endswith(".pdf") else (cleaned or "profile") + ".pdf"
    )


def fingerprint(file: FileInput) -> str:
    url = urlparse(file.url)
    # Drop known URL signing parameters, but preserve parameters that identify the file.
    signing = {"signature", "expires", "policy", "key-pair-id", "token"}
    query = [
        (k, v)
        for k, v in parse_qsl(url.query)
        if not k.lower().startswith("x-amz-") and k.lower() not in signing
    ]
    stable_url = urlunparse(
        (url.scheme, url.netloc, url.path, "", urlencode(query), "")
    )
    return hashlib.sha256(
        ("\0".join((file.identity, file.version, stable_url, file.name))).encode()
    ).hexdigest()


class SafeDownloader:
    def __init__(self, hosts: tuple[str, ...], maximum: int, local: bool = False, image: bool = False):
        self.hosts, self.maximum, self.local, self.image = hosts, maximum, local, image

    def _connection(self, url: str) -> tuple[Any, str, str]:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        try:
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
        except ValueError:
            raise DocumentError(
                "Invalid document address.", code="UNSAFE_URL"
            ) from None
        loopback = self.local and host in ("127.0.0.1", "localhost")
        if (
            parsed.username
            or parsed.password
            or host.lower() not in self.hosts
            or (not loopback and (parsed.scheme != "https" or port != 443))
            or (loopback and parsed.scheme not in ("https", "http"))
        ):
            raise DocumentError(
                "Document host is not allowed. Check attachment host configuration.",
                code="UNSAFE_URL",
            )
        try:
            addresses = sorted(
                {
                    entry[4][0]
                    for entry in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
                }
            )
        except OSError:
            raise DocumentError(
                "Unable to reach document host.", code="DOWNLOAD_FAILED"
            ) from None
        if (
            not addresses
            or any(not ipaddress.ip_address(ip).is_global for ip in addresses)
            and not loopback
        ):
            raise DocumentError("Document address must be public.", code="UNSAFE_URL")
        # Connect to the checked IP, while validating TLS against the original hostname.
        # This prevents DNS rebinding between validation and the actual connection.
        if parsed.scheme == "https":
            pool = urllib3.HTTPSConnectionPool(
                addresses[0],
                port,
                assert_hostname=host,
                server_hostname=host,
                cert_reqs="CERT_REQUIRED",
                ca_certs=certifi.where(),
                timeout=urllib3.Timeout(connect=5, read=10),
                retries=False,
            )
        else:
            pool = urllib3.HTTPConnectionPool(
                addresses[0],
                port,
                timeout=urllib3.Timeout(connect=5, read=10),
                retries=False,
            )
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
        return pool, path, parsed.netloc

    @contextmanager
    def download(self, url: str) -> Iterator[tuple[BinaryIO, int]]:
        started = time.monotonic()
        result = None
        pool = None
        try:
            for _ in range(4):
                if time.monotonic() - started > 45:
                    raise DocumentError(
                        "Document download timed out.", code="DOWNLOAD_FAILED"
                    )
                pool, path, host = self._connection(url)
                result = pool.request(
                    "GET",
                    path,
                    headers={
                        "Host": host,
                        "Accept": "image/*" if self.image else "application/pdf",
                        "Accept-Encoding": "identity",
                    },
                    preload_content=False,
                    redirect=False,
                )
                if result.status in (301, 302, 303, 307, 308):
                    location = result.headers.get("Location", "")
                    result.close()
                    pool.close()
                    url = urljoin(url, location)
                    continue
                if result.status != 200:
                    raise DocumentError(
                        "Unable to download the document.", code="DOWNLOAD_FAILED"
                    )
                mime = result.headers.get("Content-Type", "").split(";")[0].lower()
                accepted = ("image/jpeg", "image/png", "image/webp", "image/heic", "application/octet-stream") if self.image else ("application/pdf", "application/octet-stream")
                if mime not in accepted:
                    raise DocumentError(
                        "The uploaded document is not a PDF.", code="INVALID_DOCUMENT"
                    )
                length = result.headers.get("Content-Length", "")
                if length.isdigit() and int(length) > self.maximum:
                    raise DocumentError(
                        "Document exceeds the configured file size limit.",
                        code="FILE_TOO_LARGE",
                    )
                with tempfile.SpooledTemporaryFile(
                    max_size=1024 * 1024, mode="w+b"
                ) as stream:
                    size = 0
                    for chunk in result.stream(65536, decode_content=False):
                        size += len(chunk)
                        if size > self.maximum:
                            raise DocumentError(
                                "Document exceeds the configured file size limit.",
                                code="FILE_TOO_LARGE",
                            )
                        if time.monotonic() - started > 45:
                            raise DocumentError(
                                "Document download timed out.", code="DOWNLOAD_FAILED"
                            )
                        stream.write(chunk)
                    stream.seek(0)
                    if not self.image and stream.read(5) != b"%PDF-":
                        raise DocumentError(
                            "The uploaded document is not a valid PDF.",
                            code="INVALID_DOCUMENT",
                        )
                    stream.seek(0)
                    yield stream, size
                    return
            raise DocumentError("Too many document redirects.", code="UNSAFE_URL")
        except DocumentError:
            raise
        except Exception:
            raise DocumentError(
                "Document download or storage failed. Retry synchronization.",
                code="DOWNLOAD_FAILED",
            ) from None
        finally:
            if result is not None:
                result.close()
            if pool is not None:
                pool.close()


class StorageService(Protocol):
    def existing(
        self, profile_id: str, source_fingerprint: str, file_name: str
    ) -> dict[str, Any] | None: ...
    def upload(
        self, profile_id: str, file: FileInput, source_fingerprint: str
    ) -> dict[str, Any]: ...
    def signed_url(
        self, pdf: dict[str, Any], download: bool = False
    ) -> dict[str, Any]: ...


class S3StorageService:
    def __init__(
        self, client: Any, bucket: str, downloader: SafeDownloader, expiry: int = 900
    ):
        self.client, self.bucket, self.downloader, self.expiry = (
            client,
            bucket,
            downloader,
            expiry,
        )

    def upload_photo(self, profile_id: str, data: bytes) -> dict[str, Any]:
        key = f"profiles/{profile_id}/current/photo.jpg"
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data,
                               ContentType="image/jpeg", ServerSideEncryption="AES256")
        return {"s3Key": key}

    def photo_url(self, photo: dict[str, Any]) -> str:
        return self.client.generate_presigned_url("get_object",
            Params={"Bucket": self.bucket, "Key": photo["s3Key"], "ResponseContentType": "image/jpeg"},
            ExpiresIn=self.expiry)

    def existing(
        self, profile_id: str, source_fingerprint: str, file_name: str
    ) -> dict[str, Any] | None:
        key = f"profiles/{profile_id}/current/profile.pdf"
        try:
            result = self.client.head_object(Bucket=self.bucket, Key=key)
            if (
                result.get("Metadata", {}).get("source-fingerprint")
                == source_fingerprint
            ):
                return {
                    "s3Key": key,
                    "fileName": safe_filename(file_name),
                    "contentType": "application/pdf",
                    "size": result["ContentLength"],
                }
        except ClientError as exc:
            if exc.response["Error"]["Code"] not in ("404", "NoSuchKey", "NotFound"):
                raise
        return None

    def upload(
        self, profile_id: str, file: FileInput, source_fingerprint: str
    ) -> dict[str, Any]:
        key = f"profiles/{profile_id}/current/profile.pdf"
        with self.downloader.download(file.url) as (stream, size):
            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=stream,
                ContentType="application/pdf",
                ServerSideEncryption="AES256",
                Metadata={"source-fingerprint": source_fingerprint},
            )
        return {
            "s3Key": key,
            "fileName": safe_filename(file.name),
            "contentType": "application/pdf",
            "size": size,
        }

    def signed_url(self, pdf: dict[str, Any], download: bool = False) -> dict[str, Any]:
        name = safe_filename(pdf["fileName"])
        disposition = ("attachment" if download else "inline") + f'; filename="{name}"'
        url = self.client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self.bucket,
                "Key": pdf["s3Key"],
                "ResponseContentType": "application/pdf",
                "ResponseContentDisposition": disposition,
            },
            ExpiresIn=self.expiry,
        )
        return {"url": url, "expiresIn": self.expiry, "fileName": name}


class LocalStorageService:
    def __init__(self, root: Path, downloader: SafeDownloader):
        self.root, self.downloader = root, downloader
        self.fingerprints: dict[str, str] = {}
        root.mkdir(parents=True, exist_ok=True)

    def upload_photo(self, profile_id: str, data: bytes) -> dict[str, Any]:
        name = profile_id + ".jpg"
        (self.root / name).write_bytes(data)
        return {"s3Key": name}

    def photo_url(self, photo: dict[str, Any]) -> str:
        return "http://127.0.0.1:8000/local-documents/" + quote(photo["s3Key"])

    def existing(
        self, profile_id: str, source_fingerprint: str, file_name: str
    ) -> dict[str, Any] | None:
        path = self.root / (profile_id + ".pdf")
        if path.exists() and self.fingerprints.get(profile_id) == source_fingerprint:
            return {
                "s3Key": profile_id,
                "fileName": safe_filename(file_name),
                "contentType": "application/pdf",
                "size": path.stat().st_size,
            }
        return None

    def upload(
        self, profile_id: str, file: FileInput, source_fingerprint: str
    ) -> dict[str, Any]:
        with self.downloader.download(file.url) as (stream, size):
            (self.root / (profile_id + ".pdf")).write_bytes(stream.read())
        self.fingerprints[profile_id] = source_fingerprint
        return {
            "s3Key": profile_id,
            "fileName": safe_filename(file.name),
            "contentType": "application/pdf",
            "size": size,
        }

    def signed_url(self, pdf: dict[str, Any], download: bool = False) -> dict[str, Any]:
        return {
            "url": f'http://127.0.0.1:8000/local-documents/{quote(pdf["s3Key"])}.pdf?download={int(download)}',
            "expiresIn": 900,
            "fileName": pdf["fileName"],
        }
