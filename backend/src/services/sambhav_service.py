"""Persistent Sambhav metadata and private, validated PDF attachments."""
from copy import deepcopy
from pathlib import Path
from uuid import uuid4
import io
import json
import time
from botocore.exceptions import ClientError
from pypdf import PdfReader
from src.errors import AppError
from src.models.profile import now_iso
from src.services.member_service import effective_member

SEEDS = json.loads((Path(__file__).resolve().parents[1] / 'sambhav_seed.json').read_text())
STATUSES = {'Not started', 'In progress', 'Completed'}
CATEGORIES = {'vision': 'visionDocuments', 'project': 'projectDocuments', 'member-profile': 'memberProfileDocuments', 'other': 'otherDocuments'}
MAX_SIZE = 20 * 1024 * 1024


def initial(seed):
    return {**seed, 'description': '', 'status': 'Not started', 'version': 0, 'updatedAt': None,
            'ideas': [dict(id=f"{seed['code']}-{slot:02}", title=f'Idea {slot}', summary='', description='', vision='',
                           status='Not started', lead=None, coLead=None, interestedMembers=[], updatedAt=None,
                           **{field: [] for field in CATEGORIES.values()}) for slot in range(1, 4)]}


def text(value, limit=5000, required=False):
    if not isinstance(value, str) or len(value) > limit or (required and not value.strip()):
        raise AppError(f'Text must contain {"1" if required else "0"}–{limit} characters.')
    return value.strip()


class SambhavService:
    def __init__(self, table, members, s3, bucket):
        self.table, self.members, self.s3, self.bucket = table, members, s3, bucket

    def get(self, slug):
        seed = next((s for s in SEEDS if s['slug'] == slug), None)
        if not seed:
            raise AppError('Domain not found.', 404, 'NOT_FOUND')
        return self.table.get_item(Key={'id': 'domain:' + slug}, ConsistentRead=True).get('Item') or initial(seed)

    def public(self, domain):
        result = deepcopy(domain)
        for key in ['id', 'updatedBy']:
            result.pop(key, None)
        for idea in result['ideas']:
            for category in CATEGORIES.values():
                idea.setdefault(category, [])
                for doc in idea[category]:
                    doc.pop('s3Key', None)
        return result

    def list(self):
        return {'domains': [self.public(self.get(s['slug'])) for s in SEEDS], 'canEdit': True}

    def save(self, domain, version, subject):
        domain = deepcopy(domain)
        domain.update(id='domain:' + domain['slug'], version=version + 1, updatedAt=now_iso(), updatedBy=subject)
        if len(json.dumps(domain, default=str).encode('utf-8')) > 350 * 1024:
            raise AppError('Domain information is too large. Shorten descriptions or reduce assignments.')
        try:
            args = {'Item': domain, 'ConditionExpression': 'attribute_not_exists(id)' if version == 0 else '#v = :v'}
            if version:
                args.update(ExpressionAttributeNames={'#v': 'version'}, ExpressionAttributeValues={':v': version})
            self.table.put_item(**args)
        except ClientError as e:
            if e.response['Error']['Code'] == 'ConditionalCheckFailedException':
                raise AppError('Someone updated this domain. Reload the latest version before saving.', 409, 'CONFLICT') from None
            raise
        return domain

    def member(self, value):
        if value is None or value == '':
            return None
        if not isinstance(value, str) or len(value) > 320:
            raise AppError('Select a member from the member directory.')
        email = value.strip().casefold()
        item = self.members.get_item(Key={'Email': email}, ConsistentRead=True).get('Item')
        if not item or item.get('Status', '').strip().casefold() != 'active':
            raise AppError('An assigned member is no longer active. Select an active member.')
        item = effective_member(item)
        return {'email': email, 'name': (item.get('Full Name') or email)[:200]}

    def update(self, slug, body, subject):
        domain = self.get(slug)
        if not isinstance(body, dict) or set(body) - {'title'} != {'version', 'description', 'status', 'ideas'}:
            raise AppError('Invalid domain update fields.')
        version = body['version']
        if type(version) is not int or version != domain['version']:
            raise AppError('Reload the latest domain before saving.', 409, 'CONFLICT')
        if not isinstance(body['status'], str) or body['status'] not in STATUSES or not isinstance(body['ideas'], list) or len(body['ideas']) != 3:
            raise AppError('A domain must have a valid status and exactly three ideas.')
        if 'title' in body:
            domain['title'] = text(body['title'], 200, True)
        domain['description'] = text(body['description'])
        domain['status'] = body['status']
        for target, change in zip(domain['ideas'], body['ideas']):
            keys = {'id', 'title', 'summary', 'description', 'vision', 'status', 'lead', 'coLead', 'interestedMembers'}
            if not isinstance(change, dict) or set(change) != keys or change['id'] != target['id'] or not isinstance(change['status'], str) or change['status'] not in STATUSES:
                raise AppError('Invalid idea fields, order or status.')
            for field in ['title', 'summary', 'description', 'vision']:
                target[field] = text(change[field], 200 if field == 'title' else 5000, field == 'title')
            target['status'] = change['status']
            target['lead'], target['coLead'] = self.member(change['lead']), self.member(change['coLead'])
            interested = change['interestedMembers']
            if not isinstance(interested, list) or len(interested) > 100:
                raise AppError('Choose at most 100 interested members per idea.')
            found = [self.member(value) for value in interested]
            if any(value is None for value in found):
                raise AppError('Invalid interested member.')
            target['interestedMembers'] = list({m['email']: m for m in found}.values())
            target['updatedAt'] = now_iso()
        return self.public(self.save(domain, version, subject))

    def idea(self, domain, idea_id):
        result = next((idea for idea in domain['ideas'] if idea['id'] == idea_id), None)
        if not result:
            raise AppError('Idea not found.', 404, 'NOT_FOUND')
        return result

    def begin_upload(self, slug, body, subject):
        if not isinstance(body, dict) or set(body) != {'ideaId', 'category', 'fileName', 'size'}:
            raise AppError('Invalid upload request.')
        idea = self.idea(self.get(slug), body['ideaId'])
        category = body['category']
        if not isinstance(category, str) or category not in CATEGORIES:
            raise AppError('Invalid document category.')
        if sum(len(idea.get(field, [])) for field in CATEGORIES.values()) >= 30:
            raise AppError('Each idea supports up to 30 PDF attachments.')
        name = text(body['fileName'], 180, True)
        if not name.lower().endswith('.pdf') or any(c in name for c in '/\\\r\n'):
            raise AppError('Choose a PDF file with a valid filename.')
        size = body['size']
        if type(size) is not int or not 1 <= size <= MAX_SIZE:
            raise AppError('PDFs must be no larger than 20 MB.')
        upload_id = str(uuid4()); key = f'sambhav/pending/{upload_id}.pdf'
        ticket = dict(id='upload:' + upload_id, uploadId=upload_id, slug=slug, ideaId=idea['id'], category=category,
                      fileName=name, size=size, subject=subject, s3Key=key, expiresAt=int(time.time()) + 3600)
        self.table.put_item(Item=ticket, ConditionExpression='attribute_not_exists(id)')
        post = self.s3.generate_presigned_post(Bucket=self.bucket, Key=key,
            Fields={'Content-Type': 'application/pdf', 'x-amz-server-side-encryption': 'AES256'},
            Conditions=[{'Content-Type': 'application/pdf'}, {'x-amz-server-side-encryption': 'AES256'}, ['content-length-range', size, size]], ExpiresIn=300)
        return {'uploadId': upload_id, **post}

    def finish_upload(self, slug, body, subject):
        if not isinstance(body, dict) or set(body) != {'uploadId'} or not isinstance(body['uploadId'], str):
            raise AppError('Invalid upload confirmation.')
        ticket = self.table.get_item(Key={'id': 'upload:' + body['uploadId']}, ConsistentRead=True).get('Item')
        if not ticket or ticket['slug'] != slug or ticket['subject'] != subject:
            raise AppError('Upload not found.', 404, 'NOT_FOUND')
        domain = self.get(slug); idea = self.idea(domain, ticket['ideaId'])
        for field in CATEGORIES.values():
            if any(doc['id'] == ticket['uploadId'] for doc in idea.get(field, [])):
                return self.public(domain)
        if ticket['expiresAt'] < time.time():
            raise AppError('Upload expired. Select the file again.')
        if sum(len(idea.get(field, [])) for field in CATEGORIES.values()) >= 30:
            raise AppError('Each idea supports up to 30 PDF attachments.')
        try:
            obj = self.s3.get_object(Bucket=self.bucket, Key=ticket['s3Key'])
        except ClientError as e:
            if e.response['Error']['Code'] in ['NoSuchKey', '404']:
                raise AppError('Upload is not complete. Try uploading the file again.') from None
            raise
        try:
            if obj['ContentLength'] != ticket['size'] or obj['ContentLength'] > MAX_SIZE:
                raise AppError('Uploaded file size does not match.')
            data = obj['Body'].read(MAX_SIZE + 1)
        finally:
            obj['Body'].close()
        try:
            if not data.startswith(b'%PDF-') or b'%%EOF' not in data[-2048:]:
                raise ValueError('Invalid PDF')
            pdf = PdfReader(io.BytesIO(data))
            if pdf.is_encrypted or not len(pdf.pages):
                raise ValueError('Unreadable PDF')
        except Exception:
            raise AppError('Upload a readable, non-password-protected PDF.') from None
        # Only server-validated bytes enter the final prefix. A replayed upload
        # policy can replace staging bytes but cannot replace a published PDF.
        key = f"sambhav/documents/{slug}/{idea['id']}/{uuid4()}.pdf"
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType='application/pdf', ServerSideEncryption='AES256')
        record = {'id': ticket['uploadId'], 'title': ticket['fileName'], 'fileName': ticket['fileName'],
                  'size': len(data), 'uploadedAt': now_iso(), 's3Key': key}
        idea.setdefault(CATEGORIES[ticket['category']], []).append(record)
        idea['updatedAt'] = now_iso()
        try:
            saved = self.save(domain, domain['version'], subject)
        except Exception:
            self.s3.delete_object(Bucket=self.bucket, Key=key)
            raise
        # Staged uploads expire automatically; deleting this copy is best effort.
        try:
            self.s3.delete_object(Bucket=self.bucket, Key=ticket['s3Key'])
        except ClientError:
            pass
        return self.public(saved)

    def document(self, slug, idea_id, doc_id):
        idea = self.idea(self.get(slug), idea_id)
        doc = next((d for field in CATEGORIES.values() for d in idea.get(field, []) if d['id'] == doc_id), None)
        if not doc:
            raise AppError('Document not found.', 404, 'NOT_FOUND')
        from urllib.parse import quote
        url = self.s3.generate_presigned_url('get_object', Params={'Bucket': self.bucket, 'Key': doc['s3Key'],
            'ResponseContentType': 'application/pdf', 'ResponseContentDisposition': "attachment; filename*=UTF-8''" + quote(doc['fileName'], safe='')}, ExpiresIn=300)
        return {'url': url}
