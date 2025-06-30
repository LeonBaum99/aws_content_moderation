import os
import time
import pytest
import boto3
import botocore.config


#  Shared AWS clients wired to the localStack endpoint

@pytest.fixture(scope="session")
def aws_clients():
    """Return boto3 clients that talk to the current LocalStack instance."""
    endpoint = os.environ.get("AWS_ENDPOINT_URL", "http://localhost:4566")
    region   = os.environ.get("AWS_REGION", "us-east-1")

    session = boto3.Session(region_name=region)
    s3_cfg  = botocore.config.Config(s3={"addressing_style": "path"})

    return {
        "s3":       session.client("s3",        endpoint_url=endpoint, config=s3_cfg),
        "dynamodb": session.client("dynamodb",  endpoint_url=endpoint),
        "ssm":      session.client("ssm",       endpoint_url=endpoint),
        "lambda":   session.client("lambda",    endpoint_url=endpoint),
    }


#  Resource names (bucket + tables) fetched from SSM

@pytest.fixture(scope="session")
def names(aws_clients):
    """Resolve logical resource names that setup_resources.py stored in SSM."""
    ssm = aws_clients["ssm"]

    def _get(path: str) -> str:
        return ssm.get_parameter(Name=f"/app/{path}")["Parameter"]["Value"]

    return {
        "bucket":    _get("buckets/input"),
        "reviews":   _get("tables/reviews"),
        "users":     _get("tables/users"),
        "sentiment": _get("tables/sentiment"),
    }

#  Autouse session fixture – easier  lambda limits

@pytest.fixture(scope="session", autouse=True)
def relax_lambda_timeouts(aws_clients):
    """
    LocalStack deploys each lambda with Timeout of 3s by default.
    NLTK / Vader / profanity-filter imports often exceeded that during cold start, leading test to fail.
    Increase both timeout and memory so the first invocation succeeds.
    """
    lambda_client = aws_clients["lambda"]
    functions     = ("preprocess", "profanity_check", "sentiment_analysis")

    for fn in functions:
        try:
            lambda_client.update_function_configuration(
                FunctionName=fn,
                Timeout=60,    
                MemorySize=1024 # more RAM
            )
        except lambda_client.exceptions.ResourceNotFoundException as exc:
            raise RuntimeError(
                f"Lambda function '{fn}' not found. "
                "Run scripts/setup_resources.py before starting the tests."
            ) from exc

    # LocalStack applies updates asynchronously; wait a moment.
    time.sleep(2)