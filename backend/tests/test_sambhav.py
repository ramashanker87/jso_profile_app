import base64
import io
import json
import time
from copy import deepcopy
import boto3
from moto import mock_aws
from pypdf import PdfWriter
import pytest
from src.errors import AppError
from src.services.sambhav_service import SambhavService, SEEDS, CATEGORIES, MAX_SIZE
from src.handlers.api import handle
from conftest import event

@pytest.fixture
def svc():
    with mock_aws():
        session = boto3.Session(region_name='us-east-1')
        db = session.resource('dynamodb')
        table = db.create_table(TableName='sambhav', KeySchema=[{'AttributeName':'id','KeyType':'HASH'}], AttributeDefinitions=[{'AttributeName':'id','AttributeType':'S'}], BillingMode='PAY_PER_REQUEST')
        members = db.create_table(TableName='members', KeySchema=[{'AttributeName':'Email','KeyType':'HASH'}], AttributeDefinitions=[{'AttributeName':'Email','AttributeType':'S'}], BillingMode='PAY_PER_REQUEST')
        members.put_item(Item={'Email':'one@example.org','Full Name':'One','Status':'Active'})
        s3 = session.client('s3');s3.create_bucket(Bucket='test-documents')
        yield SambhavService(table,members,s3,'test-documents')

SLUG=SEEDS[0]['slug']
def changes(svc):
    domain=svc.get(SLUG)
    return {'version':int(domain['version']),'description':'Domain detail','status':'In progress','ideas':[
        {k:i[k] for k in ['id','title','summary','description','vision','status','lead','coLead','interestedMembers']} for i in domain['ideas']]}
def pdf():
    writer=PdfWriter();writer.add_blank_page(width=100,height=100);out=io.BytesIO();writer.write(out);return out.getvalue()
def upload(svc, data=None, subject='owner', category='project'):
    data=pdf() if data is None else data
    ticket=svc.begin_upload(SLUG,{'ideaId':'01-01','category':category,'fileName':'details.pdf','size':len(data)},subject)
    svc.s3.put_object(Bucket=svc.bucket,Key=ticket['fields']['key'],Body=data)
    return ticket


def test_seed_update_persistence_and_concurrency(svc):
    assert len(svc.list()['domains'])==9
    assert all(len(d['ideas'])==3 for d in svc.list()['domains'])
    body=changes(svc);body['ideas'][0]['title']='Community finance';body['ideas'][0]['lead']=' ONE@example.org '
    updated=svc.update(SLUG,body,'owner')
    assert updated['ideas'][0]['lead']=={'email':'one@example.org','name':'One'}
    assert updated['version']==1 and updated['updatedAt']
    assert svc.list()['domains'][0]['ideas'][0]['title']=='Community finance'
    with pytest.raises(AppError) as exc:svc.update(SLUG,body,'other')
    assert exc.value.status==409

@pytest.mark.parametrize('change', [lambda b:b.update(slug='changed'), lambda b:b.update(ideas=[]), lambda b:b['ideas'][0].update(id='09-01'), lambda b:b['ideas'][0].update(lead='missing@example.org'), lambda b:b.update(status=[]), lambda b:b['ideas'][0].update(title='')])
def test_invalid_changes_do_not_write(svc,change):
    body=changes(svc);change(body)
    with pytest.raises(AppError):svc.update(SLUG,body,'owner')
    assert svc.get(SLUG)['version']==0


def test_multiple_private_pdfs_and_edit_preserves_attachments(svc):
    tickets=[]
    for category in CATEGORIES:
        t=upload(svc,category=category);tickets.append(t)
        result=svc.finish_upload(SLUG,{'uploadId':t['uploadId']},'owner')
        assert 's3Key' not in json.dumps(result, default=str)
        assert len(result['ideas'][0][CATEGORIES[category]])==1
    result=svc.finish_upload(SLUG,{'uploadId':tickets[0]['uploadId']},'owner')
    assert result['version']==4  # Retry does not duplicate a file.
    svc.update(SLUG,changes(svc),'owner')
    assert len(svc.get(SLUG)['ideas'][0]['projectDocuments'])==1
    link=svc.document(SLUG,'01-01',tickets[0]['uploadId'])['url']
    assert 'sambhav/documents/' in link and 'attachment' in link
    assert 's3Key' not in json.dumps(svc.list(), default=str)


def test_upload_policy_has_size_and_type_limits(svc):
    ticket=upload(svc)
    policy=json.loads(base64.b64decode(ticket['fields']['policy']))
    assert ['content-length-range',len(pdf()),len(pdf())] in policy['conditions']
    assert {'Content-Type':'application/pdf'} in policy['conditions']
    for field,value in [('size',MAX_SIZE+1),('fileName','bad.txt'),('category','bad'),('ideaId','09-01')]:
        body={'ideaId':'01-01','category':'project','fileName':'ok.pdf','size':10};body[field]=value
        with pytest.raises(AppError):svc.begin_upload(SLUG,body,'owner')


def test_invalid_pdf_other_user_and_expired_upload_cannot_publish(svc):
    ticket=upload(svc,b'not a pdf')
    with pytest.raises(AppError):svc.finish_upload(SLUG,{'uploadId':ticket['uploadId']},'owner')
    valid=upload(svc)
    with pytest.raises(AppError):svc.finish_upload(SLUG,{'uploadId':valid['uploadId']},'other')
    svc.table.update_item(Key={'id':'upload:'+valid['uploadId']},UpdateExpression='SET expiresAt = :e',ExpressionAttributeValues={':e':int(time.time())-1})
    with pytest.raises(AppError):svc.finish_upload(SLUG,{'uploadId':valid['uploadId']},'owner')
    assert svc.get(SLUG)['version']==0


def test_replayed_staging_upload_cannot_change_published_pdf(svc):
    ticket=upload(svc);svc.finish_upload(SLUG,{'uploadId':ticket['uploadId']},'owner')
    svc.s3.put_object(Bucket=svc.bucket,Key=ticket['fields']['key'],Body=b'changed')
    svc.finish_upload(SLUG,{'uploadId':ticket['uploadId']},'owner')
    doc=svc.get(SLUG)['ideas'][0]['projectDocuments'][0]
    assert svc.s3.get_object(Bucket=svc.bucket,Key=doc['s3Key'])['Body'].read()==pdf()
    with pytest.raises(AppError):svc.document(SLUG,'01-02',ticket['uploadId'])


def test_api_uses_existing_access_guard(runtime,svc):
    runtime.sambhav=svc.table;runtime.members=svc.members;runtime.storage.client=svc.s3;runtime.storage.bucket=svc.bucket
    for path in ['/sambhav','/sambhav/domain','/sambhav/upload','/sambhav/upload/complete','/sambhav/document']:
        assert handle(event(path,authenticated=False),runtime)['statusCode']==401
    assert handle(event('/sambhav'),runtime)['statusCode']==200
    req=event('/sambhav/domain','POST',json.dumps(changes(svc)));req['queryStringParameters']={'domain':SLUG}
    assert handle(req,runtime)['statusCode']==200


def test_domain_heading_persists_with_stable_identity(svc):
    body = changes(svc)
    body['title'] = '  Community development  '
    updated = svc.update(SLUG, body, 'owner')
    assert updated['title'] == 'Community development'
    assert updated['slug'] == SLUG
    assert updated['code'] == SEEDS[0]['code']
    assert svc.list()['domains'][0]['title'] == 'Community development'
    # Older clients omit title and must preserve the saved heading.
    assert svc.update(SLUG, changes(svc), 'owner')['title'] == 'Community development'


@pytest.mark.parametrize('title', ['', '   ', 'x' * 201, None, 123])
def test_invalid_domain_heading_does_not_write(svc, title):
    body = changes(svc)
    body['title'] = title
    with pytest.raises(AppError):
        svc.update(SLUG, body, 'owner')
    assert svc.get(SLUG)['version'] == 0
