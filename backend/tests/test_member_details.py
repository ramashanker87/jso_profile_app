from unittest.mock import MagicMock
import pytest
from src.errors import AppError
from src.services.member_details_service import MEMBER_COLUMNS, prepare_members, import_members


def member(**changes):
    return {"Full Name": "Example Member", "Email": " Member@Example.org ",
            "Status": " Active ", "Membership ID": "00042", "Phone": "+460001",
            "Role": "Exclude", "File Upload": "Exclude", **changes}


def test_exact_columns_normalized_key_and_text_preserved():
    items = prepare_members([member(), member(), member(Email="inactive@example.org", Status="Inactive")])
    assert len(items) == 1
    assert set(items[0]) == set(MEMBER_COLUMNS)
    assert items[0]["Email"] == "member@example.org"
    assert items[0]["Membership ID"] == "00042"
    assert items[0]["Phone"] == "+460001"


def test_invalid_email_and_conflicting_duplicates_fail_before_writing():
    with pytest.raises(AppError):
        prepare_members([member(Email="")])
    with pytest.raises(AppError):
        prepare_members([member(), member(**{"Full Name": "Another member"})])


def test_inactive_duplicate_wins():
    assert prepare_members([member(), member(Status="Inactive")]) == []


def test_import_uses_email_key():
    table = MagicMock()
    items = prepare_members([member()])
    assert import_members(table, items) == 1
    table.batch_writer.assert_called_once_with(overwrite_by_pkeys=["Email"])
    table.batch_writer.return_value.__enter__.return_value.put_item.assert_called_once_with(Item=items[0])
