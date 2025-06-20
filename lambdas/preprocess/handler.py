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
