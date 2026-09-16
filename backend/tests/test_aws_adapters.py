from contextlib import contextmanager
from io import BytesIO
from unittest.mock import Mock, patch
import boto3
from moto import mock_aws
import pytest
from src.repositories.profile_repository import DynamoProfileRepository
from src.repositories.job_repository import DynamoJobRepository
from src.services.storage_service import (
    S3StorageService,
    SafeDownloader,
    safe_filename,
    fingerprint,
)
from src.models.profile import FileInput
from src.errors import AppError, DocumentError


def test_dynamodb_scan_all_pages():
    table = Mock()
    table.scan.side_effect = [
        {"Items": [{"profileId": "a"}], "LastEvaluatedKey": {"profileId": "a"}},
        {"Items": [{"profileId": "b"}]},
    ]
    assert len(DynamoProfileRepository(table).all()) == 2
    assert table.scan.call_args.kwargs["ExclusiveStartKey"] == {"profileId": "a"}


@mock_aws
def test_conditional_writes_and_sync_lock():
    db = boto3.resource("dynamodb", region_name="us-east-1")
    for name, key in [("profiles", "profileId"), ("jobs", "jobId")]:
        db.create_table(
            TableName=name,
            KeySchema=[{"AttributeName": key, "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": key, "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
    repo = DynamoProfileRepository(db.Table("profiles"))
    assert repo.save({"profileId": "one"}, 0)["revision"] == 1
    with pytest.raises(AppError):
        repo.save({"profileId": "one"}, 0)
    jobs = DynamoJobRepository(
        db.Table("jobs"), boto3.client("dynamodb", region_name="us-east-1")
    )
    first = jobs.start()
    with pytest.raises(AppError):
        jobs.start()
    first["status"] = "COMPLETED"
    jobs.save(first)
    assert jobs.start()["jobId"] != first["jobId"]


@mock_aws
def test_s3_upload_recovery_and_presigned_url():
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="test-profile-docs")
    downloader = Mock()

    @contextmanager
    def download(url):
        yield BytesIO(b"%PDF-1.4 test"), 13

    downloader.download.side_effect = download
    service = S3StorageService(s3, "test-profile-docs", downloader)
    assert service.existing("uuid", "fingerprint", "file.pdf") is None
    document = service.upload(
        "uuid", FileInput("https://files.example/a", "../../hello.pdf"), "fingerprint"
    )
    obj = s3.head_object(
        Bucket="test-profile-docs", Key="profiles/uuid/current/profile.pdf"
    )
    assert (
        obj["ServerSideEncryption"] == "AES256"
        and obj["ContentType"] == "application/pdf"
    )
    assert service.existing("uuid", "fingerprint", "hello.pdf") is not None
    url = service.signed_url(document, True)
    assert url["expiresIn"] == 900 and "attachment" in url["url"]
    assert document["fileName"] == "hello.pdf"


def test_fingerprint_ignores_only_signature_parameters():
    assert fingerprint(
        FileInput("https://files.example/a?X-Amz-Signature=one")
    ) == fingerprint(FileInput("https://files.example/a?X-Amz-Signature=two"))
    assert fingerprint(FileInput("https://files.example/a?id=1")) != fingerprint(
        FileInput("https://files.example/a?id=2")
    )
    assert "/" not in safe_filename("../../folder\\evil.pdf")


@pytest.mark.parametrize(
    "url",
    [
        "http://files.example/a",
        "https://evil.example/a",
        "https://user:password@files.example/a",
        "https://files.example:8080/a",
    ],
)
def test_unsafe_download_url(url):
    with pytest.raises(DocumentError):
        SafeDownloader(("files.example",), 100)._connection(url)


def test_private_dns_and_pinned_public_dns():
    downloader = SafeDownloader(("files.example",), 100)
    with patch(
        "src.services.storage_service.socket.getaddrinfo",
        return_value=[(2, 1, 6, "", ("127.0.0.1", 443))],
    ):
        with pytest.raises(DocumentError):
            downloader._connection("https://files.example/a")
    with patch(
        "src.services.storage_service.socket.getaddrinfo",
        return_value=[(2, 1, 6, "", ("1.1.1.1", 443))],
    ), patch("src.services.storage_service.urllib3.HTTPSConnectionPool") as pool:
        downloader._connection("https://files.example/a")
        assert (
            pool.call_args.args[0] == "1.1.1.1"
            and pool.call_args.kwargs["server_hostname"] == "files.example"
        )


@pytest.mark.parametrize(
    "mime,content,maximum,code",
    [
        ("text/html", b"%PDF-", 100, "INVALID_DOCUMENT"),
        ("application/pdf", b"not pdf", 100, "INVALID_DOCUMENT"),
        ("application/pdf", b"%PDF-" + b"a" * 100, 20, "FILE_TOO_LARGE"),
    ],
)
def test_download_content_and_size_limits(mime, content, maximum, code):
    downloader = SafeDownloader(("files.example",), maximum)
    result = Mock(status=200, headers={"Content-Type": mime})
    result.stream.return_value = [content]
    pool = Mock()
    pool.request.return_value = result
    with patch.object(
        downloader, "_connection", return_value=(pool, "/a", "files.example")
    ):
        with pytest.raises(DocumentError) as error:
            with downloader.download("https://files.example/a"):
                pass
        assert error.value.code == code


@mock_aws
def test_worker_leases_contend_release_and_recover_after_timeout():
    from src.repositories.lock_repository import DynamoLockRepository, LockBusy

    db = boto3.resource("dynamodb", region_name="us-east-1")
    table = db.create_table(
        TableName="lease-jobs",
        KeySchema=[{"AttributeName": "jobId", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "jobId", "AttributeType": "S"}],
        BillingMode="PAY_PER_REQUEST",
    )
    locks = DynamoLockRepository(table)
    with patch("src.repositories.lock_repository.time.time", return_value=100):
        with locks.hold("profile:one"):
            with pytest.raises(LockBusy):
                with locks.hold("profile:one"):
                    pytest.fail("Two writers acquired the same profile")
            with locks.hold("profile:two"):
                pass
            # A replacement can acquire an expired lease after the old Lambda dies.
            with patch("src.repositories.lock_repository.time.time", return_value=231):
                with locks.hold("profile:one"):
                    pass
    # Exception paths release the lease too.
    with pytest.raises(ValueError):
        with locks.hold("profile:one"):
            raise ValueError("test")
    with locks.hold("profile:one"):
        pass
