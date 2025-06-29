#!/usr/bin/env python3
"""
scripts/setup_resources.py

Automated provisioning and wiring of AWS resources on LocalStack:
1. Package and deploy Lambda stubs
2. Create SSM parameters for resource names
3. Create S3 input bucket
4. Create DynamoDB table with Streams enabled
5. Configure S3 → Preprocess Lambda notifications
6. Configure DynamoDB Streams → downstream Lambdas
7. Wait for readiness and print summary

Usage:
  python scripts/setup_resources.py

Ensure Python venv is activated and requirements installed.
"""
import os
import sys
import time
import zipfile
from pathlib import Path
import boto3
import botocore
import shutil
import subprocess

# Configuration
ENDPOINT_URL = os.getenv("LOCALSTACK_ENDPOINT", "http://localhost:4566")
REGION       = os.getenv("AWS_REGION", "us-east-1")
RESOURCE_CONFIG = {
    "s3_input_bucket": "reviews-input",
    "dynamodb_table":  "reviews",
    "sentiment_table": "sentiment", # added config for sentiment table
    "ssm_parameters": {
        "/app/buckets/input": "reviews-input",
        "/app/tables/reviews": "reviews",
        "/app/tables/users": "users" ,
        "/app/tables/sentiment": "sentiment"
    },
    "lambdas": [
        "preprocess",
        "profanity_check",
        "sentiment_analysis"
    ]
}

# AWS client factory
def get_client(service_name):
    return boto3.client(
        service_name,
        endpoint_url=ENDPOINT_URL,
        region_name=REGION,
        aws_access_key_id="test",
        aws_secret_access_key="test"
    )

s3_client     = get_client("s3")
ddb_client    = get_client("dynamodb")
ssm_client    = get_client("ssm")
lambda_client = get_client("lambda")

# Section: Lambda packaging and deployment

def package_lambda(fn_name: str):
    folder = Path("lambdas") / fn_name

    zipf_path = folder / "lambda.zip"
    if zipf_path.exists():
        zipf_path.unlink()

    with zipfile.ZipFile(zipf_path, "w", zipfile.ZIP_DEFLATED) as z:
        for file in folder.rglob("*"):
            if file.is_dir() or file == zipf_path or file.name == ".DS_Store":
                continue
            z.write(file, arcname=file.relative_to(folder))

    return str(zipf_path)


def deploy_lambda(fn_name, zip_path):
    print(f"Deploying Lambda: {fn_name}")
    try:
        lambda_client.create_function(
            FunctionName=fn_name,
            Runtime="python3.11",
            Role="arn:aws:iam::000000000000:role/lambda-role",
            Handler="handler.handler",
            Code={"ZipFile": open(zip_path, 'rb').read()},
            Timeout=3,
            Environment={"Variables": {"STAGE": "local"}}
        )
    except botocore.exceptions.ClientError as e:
        code = e.response.get('Error', {}).get('Code')
        if code == 'ResourceConflictException':
            lambda_client.update_function_code(
                FunctionName=fn_name,
                ZipFile=open(zip_path, 'rb').read()
            )
        else:
            raise
    # Poll until active
    for _ in range(20):
        resp = lambda_client.get_function(FunctionName=fn_name)
        status = resp['Configuration'].get('State', 'Pending')
        if status == 'Active':
            break
        time.sleep(1)
    else:
        print(f"WARNING: {fn_name} did not become Active in time.")


def deploy_all_lambdas():
    for name in RESOURCE_CONFIG['lambdas']:
        zip_path = package_lambda(name)
        deploy_lambda(name, zip_path)
    print("All Lambdas deployed.")

# Section: SSM parameters

def create_ssm_parameters():
    for name, value in RESOURCE_CONFIG['ssm_parameters'].items():
        print(f"Putting SSM parameter {name} = {value}")
        ssm_client.put_parameter(
            Name=name,
            Value=value,
            Type="String",
            Overwrite=True
        )

# Section: S3 bucket creation

def create_s3_bucket(bucket_name):
    try:
        print(f"Creating bucket: {bucket_name}")
        s3_client.create_bucket(Bucket=bucket_name)
    except botocore.exceptions.ClientError as e:
        code = e.response.get('Error', {}).get('Code')
        if code in ('BucketAlreadyOwnedByYou', 'BucketAlreadyExists'):
            print(f"Bucket {bucket_name} exists, skipping.")
        else:
            raise
    # Confirm bucket exists
    buckets = [b['Name'] for b in s3_client.list_buckets().get('Buckets', [])]
    if bucket_name not in buckets:
        print(f"ERROR: Bucket {bucket_name} not found after creation.")

# Section: DynamoDB table creation with Streams

def create_dynamodb_table(table_name, key_name, stream_enabled=False, stream_view_type="NEW_AND_OLD_IMAGES"):
    kwargs = {
        "TableName": table_name,
        "KeySchema": [{'AttributeName': key_name, 'KeyType': 'HASH'}],
        "AttributeDefinitions": [{'AttributeName': key_name, 'AttributeType': 'S'}],
        "BillingMode": 'PAY_PER_REQUEST'
    }
    if stream_enabled:
        kwargs["StreamSpecification"] = {
            "StreamEnabled": True,
            "StreamViewType": stream_view_type
        }
    try:
        print(f"Creating DynamoDB table: {table_name}")
        ddb_client.create_table(**kwargs)
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] == 'ResourceInUseException':
            print(f"Table {table_name} exists, skipping.")
        else:
            raise
    waiter = ddb_client.get_waiter('table_exists')
    waiter.wait(TableName=table_name)
    print(f"Table {table_name} is ready.")
    # Return stream ARN only if created with stream enabled
    if stream_enabled:
        desc = ddb_client.describe_table(TableName=table_name)
        return desc['Table']['LatestStreamArn']
    return None

# Section: S3 notification configuration

def create_s3_notification(bucket_name, lambda_name):
    resp = lambda_client.get_function(FunctionName=lambda_name)
    lambda_arn = resp['Configuration']['FunctionArn']
    config = {'LambdaFunctionConfigurations':[{'LambdaFunctionArn':lambda_arn,'Events':['s3:ObjectCreated:*']}]}  # verify this event list
    print(f"Configuring S3 notifications on {bucket_name} -> {lambda_name}")
    s3_client.put_bucket_notification_configuration(Bucket=bucket_name,NotificationConfiguration=config)

# Section: DynamoDB Stream → Lambda mapping

def create_dynamodb_event_mapping(stream_arn, function_name):
    mappings = lambda_client.list_event_source_mappings(EventSourceArn=stream_arn,FunctionName=function_name).get('EventSourceMappings', [])
    if mappings:
        print(f"Mapping for {function_name} exists, skipping.")
        return
    resp = lambda_client.create_event_source_mapping(EventSourceArn=stream_arn,FunctionName=function_name,StartingPosition='TRIM_HORIZON',BatchSize=1)
    uuid = resp['UUID']
    # Poll mapping state
    for _ in range(20):
        m = lambda_client.get_event_source_mapping(UUID=uuid)
        if m['State'] == 'Enabled': break
        time.sleep(1)
    print(f"Created mapping {uuid} -> {function_name}")

# Section: Main orchestration

def main():
    deploy_all_lambdas()
    create_ssm_parameters()
    create_s3_bucket(RESOURCE_CONFIG['s3_input_bucket'])

    # Use SSM values for table names
    reviews_table_name = RESOURCE_CONFIG['ssm_parameters']['/app/tables/reviews']
    users_table_name   = RESOURCE_CONFIG['ssm_parameters']['/app/tables/users']
    sentiment_table_name = RESOURCE_CONFIG['ssm_parameters']['/app/tables/sentiment']

    # Create reviews table (with streams)
    stream_arn = create_dynamodb_table(
        table_name=reviews_table_name,
        key_name="reviewId",
        stream_enabled=True
    )
    # Create users table (no streams)
    create_dynamodb_table(
        table_name=users_table_name,
        key_name="userId",
        stream_enabled=False
    )

    # Create sentiment table (no streams)
    create_dynamodb_table(
        table_name = sentiment_table_name,
        key_name="reviewId",
        stream_enabled=False)
    
    create_s3_notification(RESOURCE_CONFIG['s3_input_bucket'], 'preprocess')
    for fn in ['profanity_check','sentiment_analysis']:
        create_dynamodb_event_mapping(stream_arn, fn)
    print("Resource setup complete. Verify with awslocal s3 ls, dynamodb scan, lambda list-functions, etc.")


if __name__ == '__main__':
    main()
