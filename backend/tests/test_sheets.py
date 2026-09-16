from unittest.mock import Mock
import pytest
from src.errors import AppError
from src.services.sheets_service import SheetMapper, GoogleSheetsClient


def row(**changes):
    return {"Full Name": "Member One", "Email": " Member@Example.com ", "Status": " Active ",
            "Membership ID": "JSO-001", "Skills/Expertise": "Teaching", **changes}


def test_email_identity_and_active_transition(runtime):
    mapper = SheetMapper()
    service = runtime.sync_service()
    assert service.upsert(mapper.parse(row())) == "created"
    assert service.upsert(mapper.parse(row(Email="member@example.com"))) == "unchanged"
    profile = runtime.profiles.all()[0]
    assert profile["email"] == "member@example.com"
    assert profile["member"]["membershipId"] == "JSO-001"
    assert len(runtime.profiles.all()) == 1
    service.upsert(mapper.parse(row(Status="Inactive")))
    assert runtime.profile_service().list()["total"] == 0
    with pytest.raises(AppError):
        runtime.profile_service().get(profile["profileId"])
    service.upsert(mapper.parse(row()))
    assert runtime.profile_service().list()["total"] == 1


def test_inactive_new_and_invalid_email(runtime):
    assert runtime.sync_service().upsert(SheetMapper().parse(row(Status="Inactive"))) == "unchanged"
    assert runtime.profiles.all() == []
    with pytest.raises(AppError):
        SheetMapper().parse(row(Email=""))


def test_existing_profile_preserves_pdf(runtime, payload):
    source = runtime.mapper().parse(payload)
    runtime.sync_service().upsert(source)
    old = runtime.profiles.all()[0]
    runtime.sync_service().upsert(SheetMapper().parse(row(Email=source.email)))
    updated = runtime.profiles.all()[0]
    assert updated["profileId"] == old["profileId"]
    assert updated["pdf"] == old["pdf"]
    assert len(runtime.profiles.all()) == 1


def test_sheet_deduplication_and_tab(runtime):
    client = GoogleSheetsClient.__new__(GoogleSheetsClient)
    client.settings = runtime.settings
    client.get_json = Mock(side_effect=[
        {"sheets": [{"properties": {"sheetId": 1259657163, "title": "Members"}}]},
        {"values": [["Full Name", "Email", "Status"], ["A", "a@example.com", "Active"],
                    ["A", " A@example.com ", "Inactive"], ["B", "b@example.com", "Active"]]}])
    entries, total = client.page(1, 20)
    assert total == 2
    assert entries[0]["Status"] == "Inactive"


def test_photo_failure_preserves_member(runtime):
    source = SheetMapper().parse(row(**{"File Upload": "https://drive.google.com/file/d/example/view"}))
    assert runtime.sync_service().upsert(source) == "failed"
    item = runtime.profiles.all()[0]
    assert item["member"]["membershipId"] == "JSO-001"
    assert item["syncStatus"] == "PARTIAL"


def test_photo_decodes_and_resizes(runtime):
    import io
    from PIL import Image
    source = io.BytesIO()
    Image.new("RGB", (1200, 900), "blue").save(source, format="PNG")
    client = GoogleSheetsClient.__new__(GoogleSheetsClient)
    client.settings = runtime.settings
    client.get_json = Mock(return_value={"mimeType": "image/png"})
    response = Mock()
    response.iter_content.return_value = [source.getvalue()]
    context = Mock()
    context.__enter__ = Mock(return_value=response)
    context.__exit__ = Mock(return_value=False)
    client.session = Mock()
    client.session.get.return_value = context
    data = client.photo("https://drive.google.com/file/d/example/view")
    with Image.open(io.BytesIO(data)) as photo:
        assert photo.format == "JPEG"
        assert photo.size == (800, 600)
    assert client.session.get.call_args.args[0] == "https://www.googleapis.com/drive/v3/files/example"


def test_photo_never_sends_credentials_to_arbitrary_hosts(runtime):
    from src.errors import DocumentError
    client = GoogleSheetsClient.__new__(GoogleSheetsClient)
    client.settings = runtime.settings
    client.session = Mock()
    with pytest.raises(DocumentError):
        client.photo("https://untrusted.example/photo.jpg")
    client.session.get.assert_not_called()


def test_sheet_mode_hides_unmatched_legacy_members(runtime, payload):
    from src.services.profile_service import ProfileService
    runtime.sync_service().upsert(runtime.mapper().parse(payload))
    service = ProfileService(runtime.profiles, runtime.storage, members_only=True)
    assert service.list()["total"] == 0
    with pytest.raises(AppError):
        service.get(runtime.profiles.all()[0]["profileId"])
