#!/usr/bin/env python3
"""
scripts/setup_resources.py

This script creates all required AWS resources in a LocalStack environment:
- SSM parameters for configuration
- S3 input bucket
- DynamoDB table with Streams enabled
- S3 notification trigger for the preprocessing Lambda
- DynamoDB Stream event mappings for downstream Lambdas

Usage:
  export LOCALSTACK_ENDPOINT=http://localhost:4566
  export AWS_REGION=us-east-1
  python scripts/setup_resources.py

Requires:
  boto3
"""
import os
import sys
import time
import boto3
import botocore

# Read LocalStack endpoint and AWS region from environment (with defaults)
ENDPOINT_URL = os.getenv("LOCALSTACK_ENDPOINT", "http://localhost:4566")
REGION = os.getenv("AWS_REGION", "us-east-1")

# Resource definitions and names
RESOURCE_CONFIG = {
    # The S3 bucket to upload raw review files
    "s3_input_bucket": "reviews-input",

    # DynamoDB table to store processed reviews and counters
    "dynamodb_table": "reviews",

    # SSM parameters mapping for dynamic configuration
    "ssm_parameters": {
        "/app/buckets/input": "reviews-input",
        "/app/tables/reviews": "reviews"
    },

    # Lambda function names to wire up as event targets
    "lambdas": {
        "preprocess": "preprocess",
        "profanity":  "profanity_check",
        "sentiment": "sentiment_analysis",
        "banning":   "banning_logic"
    }
}

# Utility to create a boto3 client pointed at LocalStack
def get_client(service_name):
    return boto3.client(
        service_name,
        endpoint_url=ENDPOINT_URL,
        region_name=REGION,
        aws_access_key_id="test",
        aws_secret_access_key="test"
    )

# Initialize clients
s3_client       = get_client("s3")
ddb_client      = get_client("dynamodb")
ssm_client      = get_client("ssm")
lambda_client   = get_client("lambda")


def create_ssm_parameters():
    """Create or overwrite SSM parameters for resource names."""
    for name, value in RESOURCE_CONFIG["ssm_parameters"].items():
        print(f"Putting SSM parameter {name} = {value}")
        ssm_client.put_parameter(
            Name=name,
            Value=value,
            Type="String",
            Overwrite=True
        )


def create_s3_bucket(bucket_name):
    """Create an S3 bucket if it does not already exist."""
    try:
        print(f"Creating bucket: {bucket_name}")
        s3_client.create_bucket(Bucket=bucket_name)
    except botocore.exceptions.ClientError as e:
        code = e.response.get("Error", {}).get("Code")
        if code in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
            print(f"Bucket {bucket_name} already exists, skipping.")
        else:
            raise


def create_dynamodb_table(table_name):
    """Create a DynamoDB table with stream enabled, return its stream ARN."""
    try:
        print(f"Creating DynamoDB table: {table_name}")
        ddb_client.create_table(
            TableName=table_name,
            KeySchema=[{"AttributeName": "reviewId", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "reviewId", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
            StreamSpecification={"StreamEnabled": True, "StreamViewType": "NEW_AND_OLD_IMAGES"}
        )
        # Wait until active
        waiter = ddb_client.get_waiter('table_exists')
        waiter.wait(TableName=table_name)
    except botocore.exceptions.ClientError as e:
        code = e.response.get("Error", {}).get("Code")
        if code == 'ResourceInUseException':
            print(f"Table {table_name} already exists, skipping creation.")
        else:
            raise
    # Retrieve the stream ARN
    desc = ddb_client.describe_table(TableName=table_name)
    stream_arn = desc['Table']['LatestStreamArn']
    print(f"DynamoDB Stream ARN: {stream_arn}")
    return stream_arn


def create_s3_notification(bucket_name, lambda_name):
    """Configure S3 bucket notification to invoke a Lambda on object creation."""
    # Retrieve Lambda ARN
    resp = lambda_client.get_function(FunctionName=lambda_name)
    lambda_arn = resp['Configuration']['FunctionArn']
    config = {
        'LambdaFunctionConfigurations': [
            {
                'LambdaFunctionArn': lambda_arn,
                'Events': ['s3:ObjectCreated:*']
            }
        ]
    }
    print(f"Configuring S3 notifications on {bucket_name} -> {lambda_name}")
    s3_client.put_bucket_notification_configuration(
        Bucket=bucket_name,
        NotificationConfiguration=config
    )


def create_dynamodb_event_mapping(stream_arn, function_name):
    """Map a DynamoDB stream to a Lambda function."""
    # Check for existing mapping
    existing = lambda_client.list_event_source_mappings(
        EventSourceArn=stream_arn,
        FunctionName=function_name
    ).get('EventSourceMappings', [])
    if existing:
        print(f"Event source mapping for {function_name} already exists, skipping.")
        return
    # Create mapping
    resp = lambda_client.create_event_source_mapping(
        EventSourceArn=stream_arn,
        FunctionName=function_name,
        StartingPosition='TRIM_HORIZON'
    )
    print(f"Created event mapping: {resp['UUID']} for {function_name}")


def main():
    print("▶️  setup_resources.py starting…")
    # 1. SSM parameters
    create_ssm_parameters()
    # 2. S3 input bucket
    create_s3_bucket(RESOURCE_CONFIG['s3_input_bucket'])
    # 3. DynamoDB table and stream
    stream_arn = create_dynamodb_table(RESOURCE_CONFIG['dynamodb_table'])
    # 4. S3 -> Preprocess Lambda
    create_s3_notification(RESOURCE_CONFIG['s3_input_bucket'], RESOURCE_CONFIG['lambdas']['preprocess'])
    # 5. DynamoDB stream -> downstream Lambdas
    for key in ('profanity', 'sentiment', 'banning'):
        create_dynamodb_event_mapping(stream_arn, RESOURCE_CONFIG['lambdas'][key])
    print("Resource setup complete.")


if __name__ == '__main__':
    main()

# -----------------------------------------------------------------------------
# .env file (create at project root)
# -----------------------------------------------------------------------------
# LOCALSTACK_ENDPOINT=http://localhost:4566
# AWS_REGION=us-east-1
