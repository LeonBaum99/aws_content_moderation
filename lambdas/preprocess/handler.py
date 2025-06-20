import os
import json
import boto3
from decimal import Decimal
from user_ops import upsert_user_review_count

# Configure LocalStack endpoint and region from environment.
host = os.getenv("LOCALSTACK_HOSTNAME", "localhost")
port = os.getenv("EDGE_PORT", "4566")
ENDPOINT = f"http://{host}:{port}"
REGION = os.getenv("AWS_REGION", "us-east-1")

# Initialize SSM client and fetch the DynamoDB table name from Parameter Store.
ssm = boto3.client(
    "ssm",
    endpoint_url=ENDPOINT,
    region_name=REGION,
    aws_access_key_id="test",
    aws_secret_access_key="test"
)
try:
    TABLE_NAME = ssm.get_parameter(Name="/app/tables/reviews")["Parameter"]["Value"]
except Exception as e:
    print("Error fetching table name from SSM:", e)
    raise

# Set up AWS resources for DynamoDB and S3, using LocalStack endpoints.
ddb = boto3.resource(
    "dynamodb",
    endpoint_url=ENDPOINT,
    region_name=REGION,
    aws_access_key_id="test",
    aws_secret_access_key="test"
)
table = ddb.Table(TABLE_NAME)

s3 = boto3.client(
    "s3",
    endpoint_url=ENDPOINT,
    region_name=REGION,
    aws_access_key_id="test",
    aws_secret_access_key="test"
)

def handler(event: dict, context) -> dict:
    """
    Lambda entrypoint for review preprocessing.
    Reads a review from S3, parses the JSON,
    and writes a stub item to DynamoDB.
    """
    print("PREPROCESS STUB EVENT:", event)

    # Read review object from S3.
    record = event["Records"][0]
    bucket = record["s3"]["bucket"]["name"]
    key = record["s3"]["object"]["key"]

    response = s3.get_object(Bucket=bucket, Key=key)
    content = response["Body"].read()

    # Parse review content as JSON.
    json_content = json.loads(content.decode("utf-8"), parse_float=Decimal)

    # Write item to DynamoDB.
    item = {
        "reviewId": key,
        "stubProcessed": True,
        "content": json_content
    }
    table.put_item(Item=item)
    print(f"Wrote stub item to DynamoDB: {item}")

    upsert_user_review_count(json_content)

    return {"status": "ok"}
