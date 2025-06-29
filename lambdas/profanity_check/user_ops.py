import os
import boto3
from decimal import Decimal
from functools import lru_cache

# ──────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────
def _endpoint() -> str:
    host = os.getenv("LOCALSTACK_HOSTNAME", "localhost")
    port = os.getenv("EDGE_PORT", "4566")
    return f"http://{host}:{port}"

@lru_cache(maxsize=1)
def _table():
    endpoint = _endpoint()
    region   = os.getenv("AWS_REGION", "us-east-1")
    ssm = boto3.client("ssm", endpoint_url=endpoint, region_name=region,
                       aws_access_key_id="test", aws_secret_access_key="test")
    users_table_name = ssm.get_parameter(Name="/app/tables/users")["Parameter"]["Value"]
    ddb = boto3.resource("dynamodb", endpoint_url=endpoint, region_name=region,
                         aws_access_key_id="test", aws_secret_access_key="test")
    return ddb.Table(users_table_name)

# ──────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────
def register_review(reviewer_id: str) -> None:
    """
    Always increments reviewCount, creates row if absent.
    """
    tbl = _table()
    tbl.update_item(
        Key={"userId": reviewer_id},
        UpdateExpression=(
            "SET reviewCount   = if_not_exists(reviewCount, :z) + :one, "
            "    unpoliteCount = if_not_exists(unpoliteCount, :z), "
            "    banned        = if_not_exists(banned, :f)"
        ),
        ExpressionAttributeValues={
            ":z":    Decimal(0),
            ":one":  Decimal(1),
            ":f":    False
        }
    )

def register_profanity(reviewer_id: str, threshold: int = 3) -> None:
    """
    Increments unpoliteCount and sets banned=True if threshold reached.
    """
    tbl = _table()
    tbl.update_item(
        Key={"userId": reviewer_id},
        UpdateExpression="ADD unpoliteCount :one",
        ExpressionAttributeValues={":one": Decimal(1)}
    )
    # fetch current count to decide banning
    user = tbl.get_item(Key={"userId": reviewer_id}).get("Item", {})
    if user and user.get("unpoliteCount", 0) >= threshold and not user.get("banned", False):
        tbl.update_item(
            Key={"userId": reviewer_id},
            UpdateExpression="SET banned = :t",
            ExpressionAttributeValues={":t": True}
        )
