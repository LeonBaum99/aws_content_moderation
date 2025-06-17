# Environment Setup & Framework Overview

This document guides you from a fresh clone to a fully wired, stubbed serverless pipeline on LocalStack. It serves both **team members** (developers) and **AI assistants**, providing clear instructions, architecture details, and development guidelines.

---

## Setup & Initialization

1. **Prerequisites**
   - **Docker** (Engine or Desktop) installed and running
   - **Python 3.11** installed (via pyenv or system)
   - **Git**

2. **Clone and Prepare**
   ```bash
   git clone <repo-url>
   cd <repo-folder>
   python3.11 -m venv .venv
   source .venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. **Start LocalStack**
   ```bash
   LOCALSTACK_ACTIVATE_PRO=0 LOCALSTACK_DEBUG=1 localstack start
   ```
   Leave this terminal open; LocalStack will emulate AWS services on `localhost:4566`.

4. **Provision Resources**
   In a second terminal (venv active):
   ```bash
   source .venv/bin/activate
   python scripts/setup_resources.py
   ```
   This single command:
   - Packages & deploys all Lambda stubs
   - Creates SSM parameters for `reviews-input` (bucket) and `reviews` (table)
   - Creates the S3 bucket `reviews-input`
   - Creates the DynamoDB table `reviews` with Streams enabled
   - Configures S3 → `preprocess` notifications
   - Configures DynamoDB Streams → downstream Lambdas (`profanity_check`, `sentiment_analysis`, `banning_logic`)

5. **Verification**
   ```bash
   awslocal s3 ls
   awslocal lambda list-functions
   awslocal dynamodb scan --table-name reviews
   ```
   Expect to see the bucket, four Lambda names, and (initially) an empty or stub-populated table.

---

## Component Interaction & Event Flow

A review JSON flows through the following pipeline:

- **S3 Input**: Upload to `reviews-input` bucket triggers the **Preprocess Lambda** (`s3:ObjectCreated:*`).
- **Preprocess Lambda**: Reads S3 event, writes `{reviewId, stubProcessed:true}` into DynamoDB table `reviews`.
- **DynamoDB Streams**: On `INSERT`, streams record to three Lambdas in parallel:
  - **Profanity Check** (`profanity_check`)
  - **Sentiment Analysis** (`sentiment_analysis`)
  - **Banning Logic** (`banning_logic`)

**AI Note:**
- **S3 event JSON** example:
  ```json
  {"Records":[{"s3":{"object":{"key":"test.json"}}}]}
  ```
- **DynamoDB stream record** example:
  ```json
  {"Records":[{"dynamodb":{"NewImage":{...},"StreamViewType":"NEW_AND_OLD_IMAGES"}}]}
  ```

Behind the scenes:
- `put_bucket_notification_configuration` ties S3 events to Lambda ARN.
- `create_event_source_mapping` ties DynamoDB stream ARN to each Lambda, polling until `State==Enabled`.

---

## Developing Lambda Handlers

All handler code lives in `lambdas/<function>/handler.py`. After editing:
```bash
cd lambdas/<function>
zip -j lambda.zip handler.py
awslocal lambda update-function-code --function-name <function> --zip-file fileb://lambdas/<function>/lambda.zip
```

Environment variables available inside handlers:
- `STAGE=local`
- `LOCALSTACK_ENDPOINT` (default: `http://localhost:4566`)
- `AWS_REGION` (default: `us-east-1`)

**Configuration via SSM**
```python
import os, boto3
ssm = boto3.client('ssm', endpoint_url=os.getenv('LOCALSTACK_ENDPOINT'), region_name=os.getenv('AWS_REGION'))
bucket = ssm.get_parameter(Name='/app/buckets/input')['Parameter']['Value']
```

**Parsing events and writing data**
```python
# S3 event
record = event['Records'][0]
key = record['s3']['object']['key']

# DynamoDB put
table = boto3.resource('dynamodb', endpoint_url=..., region_name=...).Table('reviews')
table.put_item(Item={...})
```

---

---

## Technical Background & Event Mechanics

**How Events Are Triggered and Delivered:**
- **S3 Notifications:** When a new object is created in the `reviews-input` bucket, S3 generates an `ObjectCreated` event. LocalStack’s S3 service intercepts the upload and asynchronously invokes the configured Lambda via its API gateway. Under the hood, LocalStack maps the S3 bucket notification configuration to a LambdaFunctionConfigurations rule and posts a JSON payload matching AWS’s `s3:ObjectCreated:*` schema to the Lambda invocation endpoint.

- **DynamoDB Streams:** The `reviews` table is created with `StreamSpecification` set to `NEW_AND_OLD_IMAGES`. Every write (`PutItem`) causes a change record to be appended to an internal Kinesis-like stream. LocalStack simulates this by storing stream records in-memory and dispatching them to any Lambda functions bound via `create_event_source_mapping`. The mapping polls the stream shard, retrieves batches of records, and invokes the Lambda with a payload conforming to AWS’s DynamoDB stream record format.

- **Lambda Invocation:** Lambdas in LocalStack run as Docker containers. When S3 or DynamoDB triggers an event, LocalStack issues an HTTP request to the container’s internal endpoint (using the `FunctionArn` and `Handler`), passing the event JSON. The container executes `handler(event, context)` and returns a response. Logs are captured by LocalStack and printed to the terminal.

**LocalStack Internals Relevant to This Project:**
- LocalStack emulates AWS APIs by listening on port 4566. All `awslocal` or boto3 calls directed at `endpoint_url=http://localhost:4566` are routed to the in-memory implementations.
- Services like S3 and DynamoDB maintain state in ephemeral storage. Stopping LocalStack clears all data, so provisioning must be scripted.
- Event wiring (bucket notifications, stream mappings) is persisted only in LocalStack’s runtime memory. The setup script recreates these configurations on each fresh start.

**AWS Lambda Mechanics:**
- **Packaging:** Lambda code and dependencies are zipped and uploaded. LocalStack unpacks these into a container image for each function.
- **Concurrency & Isolation:** Each invocation runs in an isolated container process with its own `/tmp` storage.
- **Timeouts & Retries:** Configured timeouts apply; on failure LocalStack does not retry by default, mirroring AWS.

---

## Troubleshooting & Best Practices

- **HandlerNotFound**: Ensure `lambda.zip` contains a non-empty `handler.py` at zip root.
- **Idempotent setup**: Re-run `scripts/setup_resources.py` after stopping LocalStack to reset infra.
- **Quick checks**:
  ```bash
  awslocal s3api get-bucket-notification-configuration --bucket reviews-input
  awslocal dynamodb describe-table --table-name reviews --query 'Table.StreamSpecification'
  awslocal lambda list-event-source-mappings --function-name profanity_check
  ```
- **Logs**: View LocalStack logs in Terminal A for detailed AWS API call traces.

AI Note: LocalStack uses dummy creds; Boto3 clients must specify `endpoint_url` and `region_name`.

---

This documentation ensures any team member or AI assistant can fully reconstruct and understand the environment, workflow, and how to extend the stubbed pipeline with real logic.

