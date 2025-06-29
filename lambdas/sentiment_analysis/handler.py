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

ssm = boto3.client(
    "ssm",
    endpoint_url=ENDPOINT,
    region_name=REGION,
    aws_access_key_id="test",
    aws_secret_access_key="test"
)

TABLE_NAME = ssm.get_parameter(Name="/app/tables/reviews")["Parameter"]["Value"]



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
                
        review_text = new_image['content']['S']
        
        
        overall = new_image['overall']['N'] # This is a score from 1-5

        overall = float(overall)

        scores = analyzer.polarity_scores(review_text)
        compound = scores["compound"]
        
        if compound >=  0.05:
            sentiment = "POSITIVE"
        elif compound <= -0.05:
            sentiment = "NEGATIVE"
        else:
            sentiment = "NEUTRAL"


        overall = float(overall)
        # Combine the "overall" and the sentiment of the review
        if overall is None:
            final_sentiment = sentiment  # fallback
        else:
            if sentiment == "NEUTRAL":
                if overall >= 4.0:
                    final_sentiment = "POSITIVE"
                elif overall <= 2.0:
                    final_sentiment = "NEGATIVE"
                else:
                    final_sentiment = "NEUTRAL"
            elif sentiment == "POSITIVE":
                if overall <= 2.0:
                    final_sentiment = "NEUTRAL"  # contradiction
                else:
                    final_sentiment = "POSITIVE"
            elif sentiment == "NEGATIVE":
                if overall >= 4.0:
                    final_sentiment = "NEUTRAL"  # contradiction
                else:
                    final_sentiment = "NEGATIVE"
            else:
                final_sentiment = sentiment  # fallback
        
    
        item = {
            'reviewId': review_id,
            'sentiment': final_sentiment
        }
        
        table.put_item(Item=item)

        print("Sentiment from Text:", sentiment)
        print("score from rating", overall)
        
        
    except Exception as e:
        print("ERROR processing event:", event)
        print("Exception:", e)
        raise e 

    return {"status": "ok"}
