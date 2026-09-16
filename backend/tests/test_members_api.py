import json
from unittest.mock import Mock
from conftest import event
from src.handlers.api import handle


def member(email="member@example.org", **values):
    return {"Full Name": "Example Member", "Email": email, "Status": "Active", "Membership ID": "00199", **values}


def test_member_list_auth_pagination_and_search(runtime):
    runtime.members = Mock()
    runtime.members.scan.side_effect = [
        {"Items": [member(), member("inactive@example.org", Status="Inactive")], "LastEvaluatedKey": {"Email": "next@example.org"}},
        {"Items": [member("other@example.org", **{"Membership ID": "OTHER"})]}]
    assert handle(event('/members', authenticated=False), runtime)["statusCode"] == 401
    request = event('/members')
    request['queryStringParameters'] = {'search': '00199', 'pageSize': '1'}
    result = handle(request, runtime)
    assert result['statusCode'] == 200
    data = json.loads(result['body'])
    assert data['totalProfiles'] == 2
    assert data['total'] == 1
    assert data['items'][0]['member']['membershipId'] == '00199'
    assert runtime.members.scan.call_count == 2


def test_member_detail_email_and_not_found(runtime):
    runtime.members = Mock()
    runtime.members.get_item.return_value = {'Item': member('member+test@example.org')}
    request = event('/members/detail')
    request['queryStringParameters'] = {'email': ' Member+Test@Example.org '}
    assert handle(request, runtime)['statusCode'] == 200
    runtime.members.get_item.assert_called_once_with(Key={'Email': 'member+test@example.org'}, ConsistentRead=True)
    runtime.members.get_item.return_value = {'Item': member(Status='Inactive')}
    assert handle(request, runtime)['statusCode'] == 404


def test_members_invalid_page(runtime):
    runtime.members = Mock()
    request = event('/members')
    for page in ('0', 'bad'):
        request['queryStringParameters'] = {'page': page}
        assert handle(request, runtime)['statusCode'] == 400
    runtime.members.scan.assert_not_called()


def test_member_photo_links_and_unique_id_search(runtime):
    runtime.members = Mock()
    item = member(**{'Unique ID': 'UNIQUE-42', 'Photo': {'s3Key': 'profiles/member/photo.jpg'}})
    runtime.members.scan.return_value = {'Items': [item]}
    runtime.storage.photo_url.return_value = 'https://private.example/photo'
    request = event('/members')
    request['queryStringParameters'] = {'search': 'UNIQUE-42'}
    response = json.loads(handle(request, runtime)['body'])
    assert response['total'] == 1
    assert response['items'][0]['photoUrl'] == 'https://private.example/photo'
    runtime.storage.photo_url.assert_called_once_with(item['Photo'])


def test_country_filter_groups_aliases_before_pagination(runtime):
    runtime.members = Mock()
    runtime.members.scan.return_value = {'Items': [
        member('a@example.org', Country='USA'), member('b@example.org', Country='United States'),
        member('c@example.org', Country=' usa '), member('d@example.org', Country='Sweden'),
        member('e@example.org', Country=''), member('f@example.org', Country='UAE and Oman'),
        member('g@example.org', Country='Japan', Status='Inactive')]}
    request = event('/members')
    request['queryStringParameters'] = {'country': 'United States', 'pageSize': '2', 'page': '2'}
    data = json.loads(handle(request, runtime)['body'])
    assert data['total'] == 3 and len(data['items']) == 1
    assert data['totalProfiles'] == 6
    assert data['countries'] == ['Not specified', 'Oman', 'Sweden', 'United Arab Emirates', 'United States']
    request['queryStringParameters'] = {'country': 'USA', 'search': 'b@example.org'}
    assert json.loads(handle(request, runtime)['body'])['total'] == 1
    request['queryStringParameters'] = {'country': 'Not specified'}
    assert json.loads(handle(request, runtime)['body'])['items'][0]['email'] == 'e@example.org'
    request['queryStringParameters'] = {'country': 'Oman'}
    assert json.loads(handle(request, runtime)['body'])['total'] == 1


def test_map_counts_all_pages_and_country_filter_does_not_shrink_map(runtime):
    runtime.members = Mock()
    runtime.members.scan.side_effect = [
        {'Items': [member('a@example.org', Country='USA'), member('b@example.org', Country='United States')], 'LastEvaluatedKey': {'Email': 'next'}},
        {'Items': [member('c@example.org', Country='SE'), member('d@example.org', Country='', Address='Example street, Stockholm, Sweden'), member('e@example.org', Country='Unknown'), member('f@example.org', Country='USA', Status='Inactive')]}]
    data = runtime.member_service().list(country='USA', page_size=1)
    assert data['total'] == 2 and len(data['items']) == 1
    assert data['mapTotal'] == 5
    assert data['countryCounts'] == [{'country': 'Sweden', 'count': 2}, {'country': 'United States', 'count': 2}, {'country': 'Unknown', 'count': 1}]


def test_map_uses_personal_edits_and_country_before_address(runtime):
    runtime.members = Mock()
    runtime.members.scan.return_value = {'Items': [
        member('a@example.org', Country='USA', Address='Stockholm, Sweden', SelfEdits={'Country': 'Canada'}),
        member('b@example.org', Country='UAE and Oman'),
        member('c@example.org', Country='', Address='Unrecognized street 42') ]}
    data = runtime.member_service().list()
    assert data['countryCounts'] == [{'country': 'Canada', 'count': 1}, {'country': 'Not specified', 'count': 1}, {'country': 'Oman', 'count': 1}, {'country': 'United Arab Emirates', 'count': 1}]
    assert data['mapTotal'] == 3


def test_map_counts_follow_search_and_address_fallback_filter(runtime):
    runtime.members = Mock()
    runtime.members.scan.return_value = {'Items': [member('a@example.org', Address='Toronto, Canada'), member('b@example.org', Country='Sweden')]}
    data = runtime.member_service().list(search='Toronto', country='Canada')
    assert data['countryCounts'] == [{'country': 'Canada', 'count': 1}]
    assert data['mapTotal'] == data['total'] == 1


def test_map_normalizes_known_country_typo():
    from src.services.member_service import location_countries
    assert location_countries({"Country": "United Kungdom"}) == ["United Kingdom"]
