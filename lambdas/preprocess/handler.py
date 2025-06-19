import os
import json
import boto3
from decimal import Decimal

# LocalStack endpoint and region (matches setup script)
host = os.getenv("LOCALSTACK_HOSTNAME", "localhost")
port = os.getenv("EDGE_PORT", "4566")
ENDPOINT = f"http://{host}:{port}"
REGION = os.getenv("AWS_REGION", "us-east-1")

# DynamoDB table name (stub uses a fixed name; real code will read from SSM)
TABLE_NAME = "reviews"

# Initialize DynamoDB resource
ddb = boto3.resource(
    "dynamodb",
    endpoint_url=ENDPOINT,
    region_name=REGION,
    aws_access_key_id="test",
    aws_secret_access_key="test"
)
table = ddb.Table(TABLE_NAME)

s3 = boto3.client(
        's3',
        endpoint_url=ENDPOINT,
        region_name=REGION,
        aws_access_key_id="test",
        aws_secret_access_key="test"
    )

def handler(event, context):
    print("PREPROCESS STUB EVENT:", event)

    # Extract the S3 object key from the event
    record = event["Records"][0]
    bucket = event['Records'][0]['s3']['bucket']['name']
    key    = record["s3"]["object"]["key"]

    print("\n" + "="*50)
    print("DEBUG: Inspecting event structure and object access:")
    print("="*50)

    # Print the whole event
    print("Full event:\n", json.dumps(event, indent=4))

    # Print event['Records']
    print("\nevent['Records']:\n", json.dumps(event['Records'], indent=4))

    # Print event['Records'][0]
    print("\nevent['Records'][0]:\n", json.dumps(record, indent=4))

    # Print event['Records'][0]['s3']
    print("\nevent['Records'][0]['s3']:\n", json.dumps(record['s3'], indent=4))

    # Print event['Records'][0]['s3']['object']
    print("\nevent['Records'][0]['s3']['object']:\n", json.dumps(record['s3']['object'], indent=4))

    # Print event['Records'][0]['s3']['object']['key']
    print("\nevent['Records'][0]['s3']['object']['key']:\n", record['s3']['object']['key'])

    print("="*50 + "\n")

    response = s3.get_object(Bucket=bucket, Key=key)
    content = response['Body'].read()  # This is bytes

    json_content = json.loads(content.decode('utf-8'), parse_float=Decimal)


    # Write a minimal item to DynamoDB
    item = {
        "reviewId": key,
        "stubProcessed": True,
        "content": json_content
    }
    table.put_item(Item=item)
    print(f"Wrote stub item to DynamoDB: {item}")

    return {"status": "ok"}
