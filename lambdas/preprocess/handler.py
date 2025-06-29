import os
import json
import boto3
from decimal import Decimal
from user_ops import register_review
import re
import pathlib

import nltk

# 1) Ordner 'nltk_data' relativ zu dieser Datei finden
ROOT = pathlib.Path(__file__).parent
NLTK_DATA = ROOT / "nltk_data"
STOP_FILE = ROOT / "stopwords.txt"

# 2) Falls er existiert -> zu den nltk-Suchpfaden hinzufügen
if NLTK_DATA.exists():
    nltk.data.path.append(str(NLTK_DATA))

if not STOP_FILE.exists():
    raise FileNotFoundError(f"stopwords file not found: {STOP_FILE}")

with STOP_FILE.open(encoding="utf-8") as fh:
    STOP_WORDS = {
        ln.strip().lower()
        for ln in fh
        if ln.strip() and not ln.lstrip().startswith("#")
    }


from nltk.stem import WordNetLemmatizer
from nltk.tokenize import word_tokenize


LEMMATISER = WordNetLemmatizer()
ALPHA_RE = re.compile(r"[A-Za-z]+")


# Configure LocalStack endpoint and region from environment.
host = os.getenv("LOCALSTACK_HOSTNAME", "localhost")
port = os.getenv("EDGE_PORT", "4566")
ENDPOINT = f"http://{host}:{port}"
REGION = os.getenv("AWS_REGION", "us-east-1")

# Initialize SSM client and fetch the DynamoDB table name from Parameter Store.
ssm = boto3.client(
    "ssm",
    endpoint_url=ENDPOINT,
    region_name=REGION,
    aws_access_key_id="test",
    aws_secret_access_key="test"
)
try:
    TABLE_NAME = ssm.get_parameter(Name="/app/tables/reviews")["Parameter"]["Value"]
except Exception as e:
    print("Error fetching table name from SSM:", e)
    raise

# Set up AWS resources for DynamoDB and S3, using LocalStack endpoints.
ddb = boto3.resource(
    "dynamodb",
    endpoint_url=ENDPOINT,
    region_name=REGION,
    aws_access_key_id="test",
    aws_secret_access_key="test"
)
table = ddb.Table(TABLE_NAME)

s3 = boto3.client(
    "s3",
    endpoint_url=ENDPOINT,
    region_name=REGION,
    aws_access_key_id="test",
    aws_secret_access_key="test"
)

def handler(event: dict, context) -> dict:
    """
    Lambda entrypoint for review preprocessing.
    Reads a review from S3, parses the JSON,
    and writes a stub item to DynamoDB.
    """
    print("PREPROCESS STUB EVENT:", event)

    # Read review object from S3.
    record = event["Records"][0]
    bucket = record["s3"]["bucket"]["name"]
    key = record["s3"]["object"]["key"]

    response = s3.get_object(Bucket=bucket, Key=key)
    content = response["Body"].read()

    # Parse review content as JSON.
    json_content = json.loads(content.decode("utf-8"), parse_float=Decimal)


    reviewer_id = json_content.get("reviewerID")
    register_review(reviewer_id)


    # Preprocessing code 
    reviewText = json_content.get("reviewText")
    summary = json_content.get("summary")
    overall = json_content.get("overall")


    def preprocess(summary: str, review_text: str) -> str:
        """
        Combine summary + reviewText, then:
        1) lower-case & tokenise
        2) keep alphabetic tokens only
        3) remove English stop-words
        4) lemmatise (WordNet)
        Returns a single space-separated string.
        """
        raw = f"{summary} {review_text}".lower()
        tokens = word_tokenize(raw)                 # step 1
        tokens = [t for t in tokens if ALPHA_RE.fullmatch(t)]        # step 2
        tokens = [t for t in tokens if t not in STOP_WORDS]          # step 3
        lemmas = [LEMMATISER.lemmatize(t) for t in tokens]           # step 4
        return " ".join(lemmas)
    
    preprocessed = preprocess(summary, reviewText)


    # Write item to DynamoDB.
    item = {
        "reviewId": key,
        "reviewerId": reviewer_id,
        "content": preprocessed,
        "overall": overall
    }
    table.put_item(Item=item)
    


    return {"status": "ok"}
