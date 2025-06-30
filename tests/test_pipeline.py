"""
Comprehensive integration test for Assignment 3

What we verify
──────────────
1. A clearly positive review is stored with sentiment = "POSITIVE" and isUnpolite = False.
2. A clearly negative review is stored with sentiment = "NEGATIVE" and isUnpolite = False.
3. Four profane reviews from the **same** user:
     • each review row has isUnpolite = True  
     • users table increments unpoliteCount correctly  
     • user is banned (banned = True) after the 4th offence (threshold = 4).
"""

import json
import time
import uuid
from pathlib import Path

import pytest


pytestmark = pytest.mark.integration   # run via:  pytest -m integration -v


# ────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────
def _make_review(reviewer_id: str,
                 text: str,
                 summary: str,
                 overall: float = 5.0) -> dict:
    """Build the minimal review document the Lambda chain expects."""
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
    """Extract a Python scalar from a DynamoDB Low-Level Maps structure."""
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
    """Wait until the user row reaches the given unpoliteCount / banned state."""
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

    # 3-6 ─ Four profane reviews from the same user
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

# import json
# import time
# import uuid
# from pathlib import Path

# import pytest


# # ---------------------------------------------------------------------------
# #  Helpers
# # ---------------------------------------------------------------------------

# def _sample_reviews(n: int = 10):
#     """
#     Return `n` pseudo-random reviews drawn from reviews_devset.json
#     and assign a fresh UUID as reviewID for each one.
#     """
#     devset_path = Path(__file__).resolve().parent.parent / "reviews_devset.json"
#     with devset_path.open("r", encoding="utf-8") as fh:
#         all_reviews = [json.loads(line) for line in fh]

#     chosen = all_reviews[:n]          # deterministic slice keeps test repeatable
#     for rev in chosen:
#         rev["reviewID"] = str(uuid.uuid4())
#     return chosen


# # ---------------------------------------------------------------------------
# #  Integration test
# # ---------------------------------------------------------------------------

# pytestmark = pytest.mark.integration


# def test_full_pipeline(aws_clients, names):
#     """
#     End-to-end flow:
#       1. Upload 10 review objects to the S3 input bucket (one at a time).
#       2. After each upload, wait until the corresponding item appears
#          in the DynamoDB *reviews* table.
#     """
#     s3  = aws_clients["s3"]
#     ddb = aws_clients["dynamodb"]
#     tbl = names["reviews"]

#     for review in _sample_reviews():
#         key = f"{review['reviewID']}.json"
#         body = json.dumps(review).encode()

#         # ---- Upload single object -------------------------------------------------
#         s3.put_object(Bucket=names["bucket"], Key=key, Body=body)

#         # ---- Poll DynamoDB for that one item --------------------------------------
#         deadline = time.time() + 60          # up to 60 s per review
#         while time.time() < deadline:
#             resp = ddb.get_item(
#                 TableName=tbl,
#                 Key={"reviewId": {"S": key}},
#                 ConsistentRead=True,
#             )
#             if "Item" in resp:
#                 break
#             time.sleep(1)
#         else:
#             pytest.fail(f"Timeout: review '{key}' never appeared in table '{tbl}'")


# # import json, random, uuid, time, pathlib, pytest
# # from botocore.exceptions import ClientError

# # pytestmark = pytest.mark.integration

# # # ---------- helpers ----------------------------------------------------------

# # THIS_DIR = pathlib.Path(__file__).resolve().parent
# # DEVSET   = THIS_DIR.parent / "reviews_devset.json"

# # BAD_VALUES = ("", None, [])
# # REPLACEMENTS = {
# #     "helpful": [0, 0],          # DynamoDB rejects empty list
# #     "summary": "N/A",
# #     "reviewerName": "Anonymous",
# #     "category": "Unknown",
# # }

# # def _sanitize(item: dict) -> dict:
# #     """Patch keys whose values DynamoDB would refuse."""
# #     for k, v in list(item.items()):
# #         if v in BAD_VALUES or (isinstance(v, list) and len(v) == 0):
# #             item[k] = REPLACEMENTS.get(k, "N/A")
# #     return item

# # def _sample_reviews(n: int = 10):
# #     """Take n random docs from the dev-set and give each a fresh reviewID."""
# #     with DEVSET.open(encoding="utf-8") as f:
# #         rows = [json.loads(line) for line in f if line.strip()]

# #     sample = random.sample(rows, n)
# #     for r in sample:
# #         r["reviewID"] = str(uuid.uuid4())
# #         _sanitize(r)
# #     return sample

# # # ---------- the test ---------------------------------------------------------

# # def test_full_pipeline(aws_clients, names):
# #     s3  = aws_clients["s3"]
# #     ddb = aws_clients["dynamodb"]

# #     reviews = _sample_reviews()
# #     # 1. upload 50 objects
# #     for r in reviews:
# #         key = f"{r['reviewID']}.json"
# #         s3.put_object(
# #             Bucket=names["bucket"],
# #             Key=key,
# #             Body=json.dumps(r).encode(),   # ensure bytes
# #         )
# #         r["s3_key"] = key

# #     # 2. wait until every review shows up (max 90 s)
# #     deadline = time.time() + 90
# #     pending  = {r["s3_key"] for r in reviews}

# #     while pending and time.time() < deadline:
# #         batch_keys = [{"reviewId": {"S": k}} for k in list(pending)[:100]]
# #         resp = ddb.batch_get_item(
# #             RequestItems={names["reviews"]: {"Keys": batch_keys, "ConsistentRead": True}}
# #         )
# #         seen = {item["reviewId"]["S"] for item in resp["Responses"].get(names["reviews"], [])}
# #         pending -= seen
# #         time.sleep(1)

# #     assert not pending, f"Timeout: {len(pending)} reviews still unprocessed"

# #     # 3. field-level assertions
# #     for r in reviews:
# #         item = ddb.get_item(
# #             TableName=names["reviews"],
# #             Key={"reviewId": {"S": r["s3_key"]}},
# #             ConsistentRead=True,
# #         )["Item"]

# #         assert "content" in item           # preprocessing Lambda ran
# #         assert "isUnpolite" in item        # profanity Lambda ran

# #         sent = ddb.get_item(
# #             TableName=names["sentiment"],
# #             Key={"reviewId": {"S": r["s3_key"]}},
# #             ConsistentRead=True,
# #         )
# #         assert "Item" in sent              # sentiment Lambda ran

# # # import json, random, uuid, time, pathlib, pytest

# # # pytestmark = pytest.mark.integration

# # # THIS_DIR = pathlib.Path(__file__).resolve().parent
# # # DEVSET = THIS_DIR.parent / "reviews_devset.json"         # adjust if needed
# # # BAD_WORDS = ["damn", "shit", "bastard", "idiot"]           # profanity-filter default list

# # # # tests/test_pipeline.py  – patch _random_reviews()

# # # COMMON = {
# # #     "asin": "TEST-ASIN-001",
# # #     "helpful": [0, 0],
# # #     "unixReviewTime": 1700000000,          # any valid int
# # #     "reviewTime": "10 10, 2023",
# # #     "category": "Books"
# # # }

# # # def _random_reviews(n=50):
# # #     with DEVSET.open(encoding="utf-8") as f:
# # #         reviews = [json.loads(line) for line in f if line.strip()]

# # #     sample = random.sample(reviews, n - 4)
# # #     for r in sample:
# # #         r["reviewID"] = str(uuid.uuid4())
# # #         r.update(COMMON)                   # ← ensure all required keys exist

# # #     rude_reviewer = str(uuid.uuid4())
# # #     rude = [{
# # #         **COMMON,                          # ← spread mandatory keys
# # #         "reviewerID": rude_reviewer,
# # #         "reviewID":  str(uuid.uuid4()),
# # #         "summary":   f"Rude #{i}",
# # #         "reviewText": f"This is {BAD_WORDS[i]}!",
# # #         "overall":   1.0                   # float, like the dev-set
# # #     } for i in range(4)]

# # #     return sample + rude, rude_reviewer

# # # def test_full_pipeline(aws_clients, names):
# # #     s3 = aws_clients["s3"]; ddb = aws_clients["dynamodb"]
# # #     reviews, rude_reviewer = _random_reviews()
# # #     # 1. upload
# # #     for r in reviews:
# # #         key = f"{r['reviewID']}.json"
# # #         s3.put_object(Bucket=names["bucket"], Key=key, Body=json.dumps(r))
# # #         r["s3_key"] = key

# # #     # 2. poll until every review processed or timeout
# # #     deadline = time.time() + 60
# # #     pending = {r["s3_key"] for r in reviews}
# # #     while pending and time.time() < deadline:
# # #         resp = ddb.batch_get_item(
# # #             RequestItems={
# # #                 names["reviews"]: {"Keys": [{"reviewId": {"S": rid}} for rid in list(pending)[:100]]}
# # #             }
# # #         )
# # #         for item in resp["Responses"].get(names["reviews"], []):
# # #             if "isUnpolite" in item:
# # #                 pending.discard(item["reviewId"]["S"])
# # #         time.sleep(1)
# # #     assert not pending, f"Timeout: {len(pending)} reviews still unprocessed"

# # #     # 3. verify every review item
# # #     for r in reviews:
# # #         item = ddb.get_item(TableName=names["reviews"],Key={"reviewId": {"S": r["s3_key"]}})["Item"]
# # #         assert "content" in item                       # preprocessing
# # #         assert "isUnpolite" in item                    # profanity flag

# # #     # 4. verify sentiment table presence
# # #     for r in reviews:
# # #         sent = ddb.get_item(TableName=names["sentiment"],Key={"reviewId": {"S": r["s3_key"]}})
# # #         assert "Item" in sent

# # #     # 5. verify banning logic
# # #     user = ddb.get_item(TableName=names["users"], Key={"reviewerId": {"S": rude_reviewer}})
# # #     attrs = user.get("Item", {})
# # #     assert int(attrs["unpoliteCount"]["N"]) == 4
# # #     assert attrs["banned"]["BOOL"] is True
