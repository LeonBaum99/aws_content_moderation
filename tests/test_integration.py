import os
import time
import subprocess
import sys
import json

import pytest
import boto3
from botocore.config import Config

# --- configure boto3 to point at LocalStack ---
LS_ENDPOINT = "http://localhost:4566"
AWSCFG = Config(
    region_name="us-east-1",
    retries={"max_attempts": 10, "mode": "standard"},
)

@pytest.fixture(scope="session", autouse=True)
def aws_clients():
    os.environ.update({
        "AWS_ACCESS_KEY_ID": "test",
        "AWS_SECRET_ACCESS_KEY": "test",
        "AWS_REGION": "us-east-1",
    })
    s3 = boto3.client("s3", endpoint_url=LS_ENDPOINT, config=AWSCFG)
    ddb = boto3.client("dynamodb", endpoint_url=LS_ENDPOINT, config=AWSCFG)
    return {"s3": s3, "ddb": ddb}

@pytest.fixture(scope="session", autouse=True)
def setup_localstack_infra():
    # Assumes your setup script is at scripts/setup_resources.py
    subprocess.check_call([sys.executable, "scripts/setup_resources.py"]) # used to be ["python", "scripts/setup_resources.py"]
    yield
    # (optional) teardown here if desired

def load_devset():
    """
    Load the development reviews set from JSON-lines format.
    """
    base = os.path.dirname(__file__)
    path = os.path.join(base, "reviews_devset.json")
    reviews = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            reviews.append(json.loads(line))
    return reviews

def upload_reviews(s3, bucket_name, reviews):
    """
    Upload each review to S3 under a numeric key ("0.json", "1.json", …)
    Returns the list of key names (without .json) to use as reviewIds.
    """
    review_ids = []
    for idx, review in enumerate(reviews):
        key = f"{idx}.json"
        s3.put_object(
            Bucket=bucket_name,
            Key=key,
            Body=json.dumps(review).encode("utf-8")
        )
        review_ids.append(str(idx))  # this will match the S3 key sans ".json"
    return review_ids

def wait_for_stub(ddb, table_name, review_ids, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = ddb.scan(TableName=table_name)
        items = resp.get("Items", [])
        processed = {
            i["reviewId"]["S"]: i.get("stubProcessed", {}).get("BOOL", False)
            for i in items
            if "reviewId" in i
        }
        if all(processed.get(rid) for rid in review_ids):
            return True
        time.sleep(1)
    return False

def test_pipeline_stubs(aws_clients):
    s3 = aws_clients["s3"]
    ddb = aws_clients["ddb"]

    bucket = "reviews-input"
    table  = "reviews"

    # 2. Load (up to 9) and upload, capturing the reviewIds (keys sans extension)
    reviews = load_devset()[:9]
    review_ids = upload_reviews(s3, bucket, reviews)

    # 3. Wait for stubProcessed == true on each of those IDs
    assert wait_for_stub(ddb, table, review_ids), "Preprocess never ran for all reviews"

    # 4. Finally, confirm stub flag exists for every uploaded item
    resp = ddb.scan(TableName=table)
    items = {i["reviewId"]["S"]: i for i in resp["Items"]}
    for rid in review_ids:
        assert rid in items, f"Missing item for reviewId={rid}"
        assert items[rid].get("stubProcessed", {}).get("BOOL") is True
