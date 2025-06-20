import os
import json
import boto3
from decimal import Decimal
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer


# LocalStack endpoint and region (matches setup script)
host = os.getenv("LOCALSTACK_HOSTNAME", "localhost")
port = os.getenv("EDGE_PORT", "4566")
ENDPOINT = f"http://{host}:{port}"
REGION = os.getenv("AWS_REGION", "us-east-1")

# DynamoDB table name (stub uses a fixed name; real code will read from SSM)
TABLE_NAME = "reviews"

analyzer = SentimentIntensityAnalyzer()



def handler(event, context):
    print("SentimentAnalysis STUB EVENT:", event)

    good_text = "This product is a good product"
    medium_text = "The color of the product is blue"
    bad_text = "I hate that product"

    scores = analyzer.polarity_scores(good_text)
    compound = scores["compound"]
    
    if compound >=  0.05:
        sentiment = "POSITIVE"
    elif compound <= -0.05:
        sentiment = "NEGATIVE"
    else:
        sentiment = "NEUTRAL"
    
    print("-------------------------------------")
    print("Our sentiment: ", sentiment)
    
    


    return {"status": "ok"}
