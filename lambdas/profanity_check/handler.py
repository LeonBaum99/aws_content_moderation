import os
import json
import boto3
from profanityfilter import ProfanityFilter
from user_ops import register_profanity


# ──────────────────────────────────────────────────────────────
# AWS / LocalStack configuration
# ──────────────────────────────────────────────────────────────
host = os.getenv("LOCALSTACK_HOSTNAME", "localhost")
port = os.getenv("EDGE_PORT", "4566")
ENDPOINT = f"http://{host}:{port}"
REGION   = os.getenv("AWS_REGION", "us-east-1")

ssm = boto3.client(
    "ssm",
    endpoint_url=ENDPOINT,
    region_name=REGION,
    aws_access_key_id="test",
    aws_secret_access_key="test"
)

REVIEWS_TABLE = ssm.get_parameter(Name="/app/tables/reviews")["Parameter"]["Value"]

ddb = boto3.resource(
    "dynamodb",
    endpoint_url=ENDPOINT,
    region_name=REGION,
    aws_access_key_id="test",
    aws_secret_access_key="test"
)
reviews_tbl = ddb.Table(REVIEWS_TABLE)

# Initialize the profanity detector once per Lambda container.
pf = ProfanityFilter()

# ──────────────────────────────────────────────────────────────
# Helper
# ──────────────────────────────────────────────────────────────
def extract_text(new_img: dict) -> str:
    """
    Build a single text string from summary and reviewText fields.
    Falls back gracefully if one is missing.
    """
    content = new_img["content"]["M"]
    summary = content.get("summary", {}).get("S", "")
    review  = content.get("reviewText", {}).get("S", "")
    return f"{summary} {review}".strip()

# ──────────────────────────────────────────────────────────────
# Lambda entrypoint
# ──────────────────────────────────────────────────────────────
def handler(event: dict, context) -> dict:
    """
    Detects profanity in the incoming review and updates
    the isUnpolite flag in the reviews table.
    """
    try:

        record      = event["Records"][0]
        event_name  = record["eventName"]

        # Ignore MODIFY/REMOVE events
        if event_name != "INSERT":
            return {"status": "skipped"}

        new_img     = event["Records"][0]["dynamodb"]["NewImage"]
        review_id   = new_img["reviewId"]["S"]
        reviewer_id = new_img["content"]["M"]["reviewerID"]["S"]
        text        = extract_text(new_img)
        is_unpolite = pf.is_profane(text)
        print(f"[profanity_check] reviewId={review_id}  is_unpolite={is_unpolite}")

        reviews_tbl.update_item(
            Key={"reviewId": review_id},
            UpdateExpression="SET isUnpolite = :u",
            ExpressionAttributeValues={":u": is_unpolite}
        )

        if is_unpolite:
            register_profanity(reviewer_id, threshold=3)

    except Exception as e:
        print("ERROR in profanity_check handler")
        print("Event:", json.dumps(event))
        print("Exception:", e)
        raise e

    return {"status": "ok"}
