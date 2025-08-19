# AWS Serverless Content Moderation
A serverless pipeline for automatic content moderation and sentiment analysis of product reviews, built on AWS Lambda, DynamoDB, and S3. The system processes review data, detects profanity, performs sentiment analysis, and tracks problematic users. The infrastructure is easily deployed on LocalStack for local testing.

The project is built to run on LocalStack for local AWS emulation. Ensure you have Docker and Python 3.11+.

For detailed instructions on how to run the application, see `run_instructions.pdf`.

## Features
- Automated review processing: Ingests review JSON files via S3.
- Preprocessing: Cleans and standardizes review data.
- Profanity Detection: Flags profane reviews, tracks user offenses, and bans repeat offenders.
- Sentiment Analysis: Classifies reviews as positive or negative.
- User Tracking: Stores offense count and ban status per user.
- Serverless, event-driven architecture for scalability and low operational overhead.

## Structure
- `lambdas/` Lambda function source code (excluded in this repo text)
  - `preprocess/` Preprocesses raw review data, store to DynamoDB.
  - `profanity_check/` Checks for profane content, tracks offenders
  - `sentiment_analysis/` Classifies sentiment of reviews
- `scripts/`
  - `get_results.py` Analyze/moderation output summary
  - `prepare_devset.py` Split review set into per-review JSON files
  - `run_devset.py` Batch-upload reviews for testing
  - `setup_resources.py` Provision AWS resources and deploy Lambdas 
- `tests/`
  - `conftest.py` # Pytest fixtures and LocalStack config
  - `test_pipeline.py` # End-to-end pipeline integration tests

## Notes
- This repo is for local development and testing. For production deployment, proper IAM roles, security, monitoring and error handling must be added.
- Contact: For questions or contributions, open an issue or PR.

### Contributors
- Leon Baumgärtner
- Stefan Hutter
- Sebastian Hoch
- Lukas Maier
- Tobias Warnicki
