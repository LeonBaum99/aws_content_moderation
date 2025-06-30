import os
import time
import pytest
import boto3
import botocore.config


# ---------------------------------------------------------------------------
#  Shared AWS clients wired to the LocalStack endpoint
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
#  Resource names (bucket + tables) fetched from SSM
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
#  Autouse session fixture – relax Lambda limits for heavy NLP imports
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def relax_lambda_timeouts(aws_clients):
    """
    LocalStack deploys each Lambda with Timeout=3 s by default.
    NLTK / Vader / profanity-filter imports often exceed that during cold-start.
    Increase both Timeout and MemorySize so the first invocation succeeds.
    """
    lambda_client = aws_clients["lambda"]
    functions     = ("preprocess", "profanity_check", "sentiment_analysis")

    for fn in functions:
        try:
            lambda_client.update_function_configuration(
                FunctionName=fn,
                Timeout=60,     # seconds
                MemorySize=1024 # MB – more RAM = faster unzip / import
            )
        except lambda_client.exceptions.ResourceNotFoundException as exc:
            raise RuntimeError(
                f"Lambda function '{fn}' not found. "
                "Run scripts/setup_resources.py before starting the tests."
            ) from exc

    # LocalStack applies updates asynchronously; wait a moment.
    time.sleep(2)


# import os
# import time
# import pytest
# import boto3
# import botocore.config


# # -----------------------------------------------------------
# #  AWS client fixtures
# # -----------------------------------------------------------

# @pytest.fixture(scope="session")
# def aws_clients():
#     """
#     Return boto3 clients wired to the LocalStack endpoint that
#     `scripts/setup_resources.py` spins up.
#     """
#     endpoint = os.environ.get("AWS_ENDPOINT_URL", "http://localhost:4566")
#     region   = os.environ.get("AWS_REGION", "us-east-1")

#     session = boto3.Session(region_name=region)

#     # Path-style addressing avoids “301 Moved Permanently” with LocalStack S3
#     s3_cfg = botocore.config.Config(s3={"addressing_style": "path"})

#     return {
#         "s3":       session.client("s3",        endpoint_url=endpoint, config=s3_cfg),
#         "dynamodb": session.client("dynamodb",  endpoint_url=endpoint),
#         "ssm":      session.client("ssm",       endpoint_url=endpoint),
#         "lambda":   session.client("lambda",    endpoint_url=endpoint),
#     }


# # -----------------------------------------------------------
# #  Helper: resolve bucket / table names from SSM
# # -----------------------------------------------------------

# @pytest.fixture(scope="session")
# def names():
#     """
#     Fetch resource names that the bootstrap script stored in SSM.
#     """
#     endpoint = os.environ.get("AWS_ENDPOINT_URL", "http://localhost:4566")
#     region   = os.environ.get("AWS_REGION", "us-east-1")

#     ssm = boto3.client("ssm", endpoint_url=endpoint, region_name=region)

#     def _get(path):
#         return ssm.get_parameter(Name=f"/app/{path}")["Parameter"]["Value"]

#     return {
#         "bucket":    _get("buckets/input"),
#         "reviews":   _get("tables/reviews"),
#         "users":     _get("tables/users"),
#         "sentiment": _get("tables/sentiment"),
#     }


# # -----------------------------------------------------------
# #  Autouse fixture: relax Lambda time-outs for LocalStack
# # -----------------------------------------------------------

# @pytest.fixture(scope="session", autouse=True)
# def relax_lambda_timeouts(aws_clients):
#     """
#     LocalStack packages each Lambda with Timeout=3 s by default.
#     Heavy NLP imports (NLTK, Vader, profanity-filter) can exceed that
#     during cold-start, especially when several objects hit S3 at once.

#     Bump Timeout and MemorySize so the pipeline completes reliably.
#     """
#     lambda_client = aws_clients["lambda"]

#     for fn in ("preprocess", "profanity_check", "sentiment_analysis"):
#         try:
#             lambda_client.update_function_configuration(
#                 FunctionName=fn,
#                 Timeout=15,      # seconds
#                 MemorySize=512   # MB – more RAM speeds up decompression & imports
#             )
#         except lambda_client.exceptions.ResourceNotFoundException as exc:
#             raise RuntimeError(
#                 f"Lambda function '{fn}' not found. "
#                 "Run scripts/setup_resources.py against LocalStack before tests."
#             ) from exc

#     # Configuration updates are asynchronous in LocalStack; give them a moment.
#     time.sleep(1)


# import json, random, uuid, time
# import pytest, boto3, os
# from botocore.config import Config

# @pytest.fixture(scope="session")
# def aws_clients():
#     session = boto3.Session(
#         aws_access_key_id="test",
#         aws_secret_access_key="test",
#         region_name="us-east-1",
#     )
#     endpoint = os.environ["AWS_ENDPOINT_URL"]
#     s3_cfg = Config(s3={"addressing_style": "path"}) # added
#     return {
#         "s3": session.client("s3", endpoint_url=endpoint, config=s3_cfg),
#         "dynamodb": session.client("dynamodb", endpoint_url=endpoint),
#         "ssm": session.client("ssm", endpoint_url=endpoint),
#     }

# @pytest.fixture(scope="session")
# def names(aws_clients):
#     ssm = aws_clients["ssm"].get_parameter
#     return {
#         "bucket": ssm(Name="/app/buckets/input")["Parameter"]["Value"],
#         "reviews": ssm(Name="/app/tables/reviews")["Parameter"]["Value"],
#         "users":   ssm(Name="/app/tables/users")["Parameter"]["Value"],
#         "sentiment": ssm(Name="/app/tables/sentiment")["Parameter"]["Value"],
#     }