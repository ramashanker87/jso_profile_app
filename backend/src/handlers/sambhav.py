import json
from src.errors import AppError
from src.handlers.http import raw_body


def handle(runtime, event, method, path):
    service = runtime.sambhav_service()
    query = event.get('queryStringParameters') or {}
    slug = query.get('domain', '')
    if method == 'GET' and path == '/sambhav':
        return service.list()
    if method == 'GET' and path == '/sambhav/domain':
        return service.public(service.get(slug))
    if method == 'GET' and path == '/sambhav/document':
        return service.document(slug, query.get('idea', ''), query.get('document', ''))
    if method == 'POST':
        try:
            body = json.loads(raw_body(event))
        except (ValueError, UnicodeError):
            raise AppError('Invalid JSON body.') from None
        subject = event['requestContext']['authorizer']['jwt']['claims']['sub']
        actions = {'/sambhav/domain': service.update, '/sambhav/upload': service.begin_upload, '/sambhav/upload/complete': service.finish_upload}
        if path in actions:
            return actions[path](slug, body, subject)
    raise AppError('Not found.', 404, 'NOT_FOUND')
