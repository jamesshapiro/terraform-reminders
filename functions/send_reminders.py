import dateutil.parser
import time
import boto3
import json
#from boto3.dynamodb.conditions import Key, Attr
import os
import ulid

lam = boto3.client('lambda')
sns_client = boto3.client('sns')
ddb_client = boto3.client('dynamodb')
table_name = os.environ['REMINDERS_DDB_TABLE']
topic = os.environ['REMINDERS_TOPIC']
phone_number = os.environ['REMINDERS_PHONE_NUMBER']
NUM_ITEMS = 100
#email_reminder_function = os.environ['EMAIL_REMINDER_FUNCTION']
#text_reminder_function = os.environ['TEXT_REMINDER_FUNCTION']
#dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
#table = dynamodb.Table('reminders')

def alert_is_due(item_ulid):
    curr_unix_time = int(str(time.time()).split(".")[0])
    curr_unix_ulid = ulid.from_timestamp(curr_unix_time)
    is_elapsed = item_ulid < curr_unix_ulid
    return is_elapsed

def get_latest_items(table_name, num_items):
    return ddb_client.query(
        TableName = table_name,
        Limit=num_items,
        ScanIndexForward=True,
        KeyConditionExpression='#pk1 = :pk1',
        ExpressionAttributeNames={
            '#pk1': 'PK1'
        },
        ExpressionAttributeValues={
            ':pk1': {'S': 'REMINDER'}
        }
    )

def process_items(items, sns_client, ddb_client, topic):
    response_items = []
    for item in items:
        item_ulid = ulid.from_str(item['SK1']['S'])
        if not alert_is_due(item_ulid):
            return response_items
        response_items.append(item)
        reminder = item['reminder']['S']

        response = sns_client.publish(
            TopicArn=topic,
            Message=reminder,
            Subject=f'REMINDER: {reminder}'
        )

        publish_sns_response = sns_client.publish(PhoneNumber=phone_number, Message=reminder)
        ddb_client.delete_item(
            TableName=table_name,
            Key = {
                'PK1': {'S': 'REMINDER'},
                'SK1': {'S': str(item_ulid)}
            }
        )

def lambda_handler(event, context):
    print(f'{topic=}')
    response = get_latest_items(table_name, NUM_ITEMS)
    
    items = response['Items']
    response_items = process_items(items, sns_client, ddb_client, topic)
    
    return response_items
