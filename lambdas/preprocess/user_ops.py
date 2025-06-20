import os
import boto3

def upsert_user_review_count(review_json: dict) -> None:
    """
    Ensures the user with reviewerID exists in the users table.
    If user does not exist, creates with reviewCount=1, profanity=0, banned=False.
    If exists, increments reviewCount by 1.
    """
    # Prepare AWS/LocalStack config
    host = os.getenv("LOCALSTACK_HOSTNAME", "localhost")
    port = os.getenv("EDGE_PORT", "4566")
    ENDPOINT = f"http://{host}:{port}"
    REGION = os.getenv("AWS_REGION", "us-east-1")
    
    # Get users table name from SSM
    ssm = boto3.client(
        "ssm",
        endpoint_url=ENDPOINT,
        region_name=REGION,
        aws_access_key_id="test",
        aws_secret_access_key="test"
    )
    users_table_name = ssm.get_parameter(Name="/app/tables/users")["Parameter"]["Value"]
    ddb = boto3.resource(
        "dynamodb",
        endpoint_url=ENDPOINT,
        region_name=REGION,
        aws_access_key_id="test",
        aws_secret_access_key="test"
    )
    table = ddb.Table(users_table_name)
    
    reviewer_id = review_json.get("reviewerID")
    if not reviewer_id:
        raise ValueError("review_json missing 'reviewerID'")
    
    # Try to increment reviewCount. If user doesn't exist, create.
    try:
        # Atomic update: will create item if not present
        table.update_item(
            Key={"userId": reviewer_id},
            UpdateExpression="SET reviewCount = if_not_exists(reviewCount, :zero) + :one, "
                             "profanity = if_not_exists(profanity, :zero), "
                             "banned = if_not_exists(banned, :false)",
            ExpressionAttributeValues={
                ":zero": 0,
                ":one": 1,
                ":false": False
            }
        )
    except Exception as e:
        print(f"Error updating/creating user {reviewer_id}: {e}")
        raise
