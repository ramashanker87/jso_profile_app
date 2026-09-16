import json
from unittest.mock import Mock
import pytest
from conftest import event
from test_member_reconciliation import table
from src.handlers.api import handle


@pytest.fixture
def editing(runtime, table):
    runtime.members = table
    runtime.cognito = Mock()
    runtime.cognito.admin_get_user.return_value = {
        "Enabled": True, "UserAttributes": [
            {"Name": "sub", "Value": "test-user"},
            {"Name": "email", "Value": "Owner@Yahoo.com"},
            {"Name": "email_verified", "Value": "true"}]}
    table.put_item(Item={"Email": "owner@yahoo.com", "Full Name": "Owner", "Status": "Active", "Country": "Sweden"})
    return runtime


def update(runtime, fields, email="owner@yahoo.com", authenticated=True):
    request = event('/members/detail', 'POST', json.dumps(fields), authenticated=authenticated)
    request['queryStringParameters'] = {'email': email}
    return handle(request, runtime)


def test_owner_edit_and_source_updates_preserve_personal_values(editing):
    result = update(editing, {'Full Name': 'Updated Owner', 'Country': 'Norway'})
    assert result['statusCode'] == 200
    assert json.loads(result['body'])['name'] == 'Updated Owner'
    editing.members.update_item(Key={'Email': 'owner@yahoo.com'}, UpdateExpression='SET Country = :c', ExpressionAttributeValues={':c': 'Denmark'})
    assert editing.member_service().get('owner@yahoo.com')['member']['country'] == 'Norway'
    assert editing.member_service().list(country='Norway')['total'] == 1
    assert editing.members.get_item(Key={'Email': 'owner@yahoo.com'})['Item']['SelfEditedBy'] == 'test-user'


def test_other_member_and_anonymous_cannot_edit(editing):
    assert update(editing, {'Full Name': 'Changed'}, 'other@example.org')['statusCode'] == 403
    assert update(editing, {'Full Name': 'Changed'}, authenticated=False)['statusCode'] == 401
    assert 'SelfEdits' not in editing.members.get_item(Key={'Email': 'owner@yahoo.com'})['Item']


@pytest.mark.parametrize('attribute,value', [('email_verified', 'false'), ('sub', 'another-user')])
def test_verified_identity_required(editing, attribute, value):
    for item in editing.cognito.admin_get_user.return_value['UserAttributes']:
        if item['Name'] == attribute:
            item['Value'] = value
    assert update(editing, {'Full Name': 'Changed'})['statusCode'] == 403


@pytest.mark.parametrize('fields', [{'Email': 'other@example.org'}, {'Status': 'Active'}, {'Membership ID': '1'}, {'SelfEdits': {}}, {'Full Name': ''}, {'Phone': 123}, {'Comments': 'x' * 4001}, [], {}])
def test_protected_fields_and_invalid_values_rejected(editing, fields):
    assert update(editing, fields)['statusCode'] == 400


def test_deleted_member_is_not_recreated(editing):
    editing.members.delete_item(Key={'Email': 'owner@yahoo.com'})
    assert update(editing, {'Full Name': 'Changed'})['statusCode'] == 404


def test_affiliation_round_trip_and_combined_filters(editing):
    result = update(editing, {'Chapter': 'Stockholm', 'Country': 'Sweden', 'Region': 'Europe'})
    assert result['statusCode'] == 200
    member = json.loads(result['body'])['member']
    assert (member['chapter'], member['country'], member['region']) == ('Stockholm', 'Sweden', 'Europe')
    service = editing.member_service()
    result = service.list(chapter='stockholm', country='Sweden', region='Europe')
    assert result['total'] == 1
    assert result['chapters'] == ['Stockholm']
    assert service.list(chapter='London', region='Europe')['total'] == 0
    assert service.list(chapter='Stockholm', region='Asia')['mapTotal'] == 0
    request = event('/members')
    request['queryStringParameters'] = {'chapter': 'London', 'region': 'Europe'}
    assert json.loads(handle(request, editing)['body'])['total'] == 0


@pytest.mark.parametrize('country,region', [('India', 'Asia'), ('UAE', 'Asia'), ('Sweden', 'Middle East'), ('Sweden', 'Invalid')])
def test_invalid_region_assignments(editing, country, region):
    assert update(editing, {'Country': country, 'Region': region})['statusCode'] == 400


def test_middle_east_alias_and_unassigned_india(editing):
    assert update(editing, {'Country': 'UAE', 'Region': 'Middle East'})['statusCode'] == 200
    assert update(editing, {'Country': 'India', 'Region': ''})['statusCode'] == 200
