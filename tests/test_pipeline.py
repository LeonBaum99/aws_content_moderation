"""
Integration test

What we verify
──────────────
- A clearly positive review is stored with sentiment = "POSITIVE" and isUnpolite = False
- A clearly negative review is stored with sentiment = "NEGATIVE" and isUnpolite = False
- Four profane reviews from the same user:
     - each review row has isUnpolite = True  
     - users table increments unpoliteCount correctly  
     - user is banned (banned = True) after the 4th offence (threshold = 4)
"""

import json
import time
import uuid
from pathlib import Path

import pytest


pytestmark = pytest.mark.integration   # run via:  pytest -m integration -v

# Helpers
def _make_review(reviewer_id: str,
                 text: str,
                 summary: str,
                 overall: float = 5.0) -> dict:
    """Build the minimal review document the lambdas expect."""
    return {
        "reviewerID":   reviewer_id,
        "asin":         "TESTASIN",
        "reviewerName": reviewer_id,
        "helpful":      [0, 0],
        "reviewText":   text,
        "overall":      overall,
        "summary":      summary,
        "unixReviewTime": 0,
        "reviewTime":   "01 1, 2020",
        "category":     "Test"
    }


def _dynamo_value(attr_map, key):
    """Extract a scalar from a dynamoDB maps structure."""
    if key not in attr_map:
        return None
    val = attr_map[key]
    if "S"   in val: return val["S"]
    if "BOOL" in val: return val["BOOL"]
    if "N"   in val: return int(float(val["N"]))
    return val


def _wait_for_review(ddb, table, key, *, expect_unpolite, timeout=60):
    """Wait until the reviews row exists and has isUnpolite set as expected."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = ddb.get_item(TableName=table,
                            Key={"reviewId": {"S": key}},
                            ConsistentRead=True)
        item = resp.get("Item")
        if item and "isUnpolite" in item:
            assert _dynamo_value(item, "isUnpolite") is expect_unpolite, (
                f"isUnpolite mismatch for {key}"
            )
            return
        time.sleep(1)
    pytest.fail(f"Timeout waiting for review {key}")


def _wait_for_sentiment(ddb, table, key, expected, timeout=60):
    """Wait until the sentiment table holds the expected label."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = ddb.get_item(TableName=table,
                            Key={"reviewId": {"S": key}},
                            ConsistentRead=True)
        item = resp.get("Item")
        if item:
            got = _dynamo_value(item, "sentiment")
            assert got == expected.upper(), f"sentiment {got} != {expected}"
            return
        time.sleep(1)
    pytest.fail(f"Timeout waiting for sentiment of {key}")


def _wait_for_user(ddb, table, user_id, *, count, banned, timeout=60):
    """Wait until the user row reaches the given unpoliteCount or banned state."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = ddb.get_item(TableName=table,
                            Key={"userId": {"S": user_id}},
                            ConsistentRead=True)
        item = resp.get("Item")
        if item and "unpoliteCount" in item:
            if (_dynamo_value(item, "unpoliteCount") >= count and
                    _dynamo_value(item, "banned") is banned):
                return
        time.sleep(1)
    pytest.fail(
        f"Timeout waiting for user {user_id}: "
        f"count>={count} banned={banned}"
    )


# ────────────────────────────────────────────────────────────────
# Main test
# ────────────────────────────────────────────────────────────────
def test_pipeline_requirements(aws_clients, names):
    s3  = aws_clients["s3"]
    ddb = aws_clients["dynamodb"]

    reviews_tbl   = names["reviews"]
    sentiment_tbl = names["sentiment"]
    users_tbl     = names["users"]
    bucket        = names["bucket"]

    # 1 ─ Positive review
    pos_review = _make_review(
        reviewer_id="user_positive",
        text="I absolutely loved this product. "
             "It works perfectly and exceeds every expectation. Amazing!",
        summary="Fantastic",
        overall=5.0
    )
    pos_key = f"{uuid.uuid4()}.json"
    s3.put_object(Bucket=bucket, Key=pos_key, Body=json.dumps(pos_review).encode())

    _wait_for_review(ddb, reviews_tbl, pos_key, expect_unpolite=False)
    _wait_for_sentiment(ddb, sentiment_tbl, pos_key, expected="POSITIVE")

    # 2 ─ Negative review
    neg_review = _make_review(
        reviewer_id="user_negative",
        text="This is the worst thing I have ever purchased. "
             "Utterly terrible and completely useless.",
        summary="Awful",
        overall=1.0
    )
    neg_key = f"{uuid.uuid4()}.json"
    s3.put_object(Bucket=bucket, Key=neg_key, Body=json.dumps(neg_review).encode())

    _wait_for_review(ddb, reviews_tbl, neg_key, expect_unpolite=False)
    _wait_for_sentiment(ddb, sentiment_tbl, neg_key, expected="NEGATIVE")

    # ─ Four profane reviews from the same user
    bad_user = "user_profane"
    for i in range(4):
        prof_review = _make_review(
            reviewer_id=bad_user,
            text="This product is shit. Totally worthless!",
            summary="Crap",
            overall=1.0
        )
        prof_key = f"{uuid.uuid4()}.json"
        s3.put_object(Bucket=bucket, Key=prof_key, Body=json.dumps(prof_review).encode())

        _wait_for_review(ddb, reviews_tbl, prof_key, expect_unpolite=True)

        expected_count  = i + 1
        expected_banned = expected_count >= 4
        _wait_for_user(ddb, users_tbl, bad_user,
                       count=expected_count,
                       banned=expected_banned)


