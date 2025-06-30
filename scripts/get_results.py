import os
import boto3
from decimal import Decimal
from functools import lru_cache
import pandas as pd

print("Script gestartet")
# ──────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────
def _endpoint() -> str:
    host = os.getenv("LOCALSTACK_HOSTNAME", "localhost")
    port = os.getenv("EDGE_PORT", "4566")
    return f"http://{host}:{port}"

@lru_cache(maxsize=1)
def _tableUsers():
    endpoint = _endpoint()
    region   = os.getenv("AWS_REGION", "us-east-1")
    ssm = boto3.client("ssm", endpoint_url=endpoint, region_name=region,
                       aws_access_key_id="test", aws_secret_access_key="test",
                       config=boto3.session.Config(connect_timeout=5, read_timeout=5))
    users_table_name = ssm.get_parameter(Name="/app/tables/users")["Parameter"]["Value"]
    ddb = boto3.resource("dynamodb", endpoint_url=endpoint, region_name=region,
                         aws_access_key_id="test", aws_secret_access_key="test")
    return ddb.Table(users_table_name)

def _tableSentiment():
    # DynamoDB table name (stub uses a fixed name; real code will read from SSM)
    TABLE_NAME = "sentiment"

    # Initialize DynamoDB resource
    ddb = boto3.resource(
        "dynamodb",
        endpoint_url=_endpoint(),
        region_name=os.getenv("AWS_REGION", "us-east-1"),
        aws_access_key_id="test",
        aws_secret_access_key="test"
    )
    return ddb.Table(TABLE_NAME)

# Read the data from the sentiment table
tbl_sent = _tableSentiment()
response_sent = tbl_sent.scan()
items_sent = response_sent['Items']

# Convert to pandas dataframe for easy evaluation
df_sent = pd.DataFrame(items_sent)

# Count the different sentiments 
freq_table = df_sent['sentiment'].value_counts()
for idx, val in freq_table.items():
    print(f"Number of {idx.lower()} reviews: {val}")


# Read the data from the user table
tbl_user = _tableUsers()
response_user = tbl_user.scan()
items_user = response_user['Items']

# Convert to pandas dataframe for easy evaluation
df_user = pd.DataFrame(items_user)

# Sum up the reviews containing profanity and banned customers
print(f"Number of reviews containing profanity: {df_user['unpoliteCount'].sum()}")
print(f"Number of banned customers: {df_user['banned'].sum()}")
