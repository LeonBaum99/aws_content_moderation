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
# Lambda entrypoint
# ──────────────────────────────────────────────────────────────
def handler(event: dict, context) -> dict:
    """
    Detects profanity in the incoming review and updates
    the isUnpolite flag in the reviews table.
    """
    try:

        new_image = event['Records'][0]['dynamodb']['NewImage']
                
        review_id = new_image['reviewId']['S']
                
        review_text = new_image['content']['S']

        reviewer_id = new_image['reviewerId']['S']

        event_name = event['Records'][0]['eventName']
        

        # Ignore MODIFY/REMOVE events
        if event_name != "INSERT":
            return {"status": "skipped"}


        is_unpolite = pf.is_profane(review_text)
        print(f"[profanity_check] reviewId={review_id}  is_unpolite={is_unpolite}")

        reviews_tbl.update_item(
            Key={"reviewId": review_id},
            UpdateExpression="SET isUnpolite = :u",
            ExpressionAttributeValues={":u": is_unpolite}
        )

        if is_unpolite:
            register_profanity(reviewer_id, threshold=4)

    except Exception as e:
        print("ERROR in profanity_check handler")
        print("Event:", json.dumps(event))
        print("Exception:", e)
        raise e

    return {"status": "ok"}
