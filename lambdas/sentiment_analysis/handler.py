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
TABLE_NAME = "sentiment"

# Initialize DynamoDB resource
ddb = boto3.resource(
    "dynamodb",
    endpoint_url=ENDPOINT,
    region_name=REGION,
    aws_access_key_id="test",
    aws_secret_access_key="test"
)
table = ddb.Table(TABLE_NAME)

analyzer = SentimentIntensityAnalyzer()



def handler(event, context):

    try: 
        print("SentimentAnalysis STUB EVENT:", event)

        new_image = event['Records'][0]['dynamodb']['NewImage']
                
        review_id = new_image['reviewId']['S']
                
        content = new_image['content']['M']
        review_text = content['reviewText']['S']
        
        # overall und summary sollen auch mit rein NICHT VERGESSEN!!!!!

        scores = analyzer.polarity_scores(review_text)
        compound = scores["compound"]
        
        if compound >=  0.05:
            sentiment = "POSITIVE"
        elif compound <= -0.05:
            sentiment = "NEGATIVE"
        else:
            sentiment = "NEUTRAL"
        
        print("-------------------------------------")
        print("Our sentiment: ", sentiment)

        item = {
            'reviewId': review_id,
            'sentiment': sentiment
        }


        print("the item to upload: ", item)
        
        table.put_item(Item=item)
        
        
    except Exception as e:
        print("ERROR processing event:", event)
        print("Exception:", e)
        raise e  # wichtig, damit LocalStack korrekt reagiert

    return {"status": "ok"}
