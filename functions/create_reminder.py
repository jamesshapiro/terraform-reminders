import json
import sys
import dateutil.parser
import time
import boto3
import os
import ulid
from base64 import b64decode

bad_time_syntax = 'Bad time syntax. Usage: "reminder": "do laundry", "time": "12-18-2016-12:09am"'

# TODO replace with API key
# ENCRYPTED = os.environ['ciphertext_password']
#password = boto3.client('kms').decrypt(CiphertextBlob=b64decode(ENCRYPTED))['Plaintext'].decode("utf-8")

def bad_request(message):
    response_code = 400
    response_body = {'feedback': message}
    response = {'statusCode': response_code,
                'headers': {'x-custom-header' : 'custom-header'},
                'body': json.dumps(response_body)}
    return response

"""
TODO: replace with API Key
def unauthorized_request():
    response_code = 401
    response_body = {'feedback': 'bad password or missing password in body'}
    response = {'statusCode': response_code,
                'headers': {'x-custom-header' : 'custom-header'},
                'body': json.dumps(response_body)}
    return response
"""

def lambda_handler(event, context):
    response_code = 200
    print("request: " + json.dumps(event))
    
    if 'body' not in event:
        return bad_request('you have to include a request body')
    body = json.loads(event['body'])
    # TODO: replace with API Gateway API Key
    # if 'password' not in body or body['password'] != password:
    #    return unauthorized_request()
    if 'reminder' not in body:
        return bad_request('the request body has to include a reminder')
    reminder_content = body['reminder']
    if 'time' not in body:
        return bad_request('the request body has to include a time')
    time_content = body['time']
    readable_reminder_time = body['readable_reminder_time']
    unix_time = int(body['time'])
    curr_unix_time = int(str(time.time()).split(".")[0])
    
    message = f'Remind James of the following: "{reminder_content}" at {readable_reminder_time}. {time_content=}. {curr_unix_time=}'

    if curr_unix_time > unix_time:
        message += f' ***WARNING: REMINDER IS IN THE PAST!*** {unix_time} < {curr_unix_time}'
    
    dynamodb_client = boto3.client('dynamodb')
    table_name = os.environ['REMINDERS_DDB_TABLE']

    reminder_ulid = str(ulid.from_timestamp(unix_time))

    response = dynamodb_client.put_item(
        TableName = table_name,
        Item={
            'PK1': {'S': 'REMINDER'},
            'SK1': {'S': reminder_ulid},
            'reminder': {'S': reminder_content}
        }
    )
    
    response_body = {
        'message': message,
        'input': event
    }
    
    response = {
        'statusCode': response_code,
        'headers': {
            'x-custom-header' : 'custom header'
        },
        'body': json.dumps(response_body)
    }
    print("response: " + json.dumps(response))
    return response