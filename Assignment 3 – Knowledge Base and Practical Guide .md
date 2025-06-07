Assignment 3 – Knowledge Base and Practical Guide  
Version: 2025-06-07

-------------------------------------------------------------------------------

1. Assignment Overview

Goal:
Implement an event-driven serverless application using AWS Lambda and related AWS PaaS services (S3, DynamoDB, SSM). The application analyzes customer reviews, performing text preprocessing, profanity check, sentiment analysis, tracking “unpolite” reviews, and banning users after more than 3 unpolite reviews.

Scope:
- Focus is on architecture and implementation of the serverless pipeline.
- Not required to maximize model accuracy or processing speed.
- Must run entirely on a local stack using LocalStack (Docker).

-------------------------------------------------------------------------------

2. Core Requirements

2.1 Lambda Functions
- At least three Lambdas are required: 
  - Preprocessing (tokenization, stop word removal, lemmatization)
  - Profanity-check
  - Sentiment-analysis
- Optionally, the counter/banning logic can be its own Lambda.

2.2 Event-Driven Workflow
- The pipeline starts when a new review is inserted into a designated S3 bucket.
- Subsequent Lambdas are triggered by S3 or DynamoDB events (not direct calls).
- If more than one Lambda must react to a single event, use EventBridge or SNS for fan-out.
- Each review must process the fields: summary, reviewText, and overall.

2.3 Configuration
- All resource names and relevant config (S3 bucket names, table names) must be stored in the AWS SSM Parameter Store.
- Lambdas must retrieve configuration dynamically from SSM, not hardcoded.

2.4 Integration Tests
- Automated integration tests must cover all main pipeline functionalities: preprocessing, profanity check, sentiment analysis, counting/banning.
- Use pytest, base your structure on the tutorial provided.

2.5 Data and Output
- Use the reviews_devset.json dataset for required output statistics.
- May add custom reviews for corner-case tests (must be included in submission but not in main results).
- Must produce:
  - Count of positive, neutral, and negative reviews
  - Number of reviews failing profanity check
  - List of banned users

2.6 Deliverables
- report.pdf: Max 8 pages, 11pt, one column. Five sections: Introduction, Problem Overview, Methodology, Results, Conclusions. Must include an architectural diagram.
- instructions.pdf: Complete instructions for setup, running, and testing the solution.
- src/: Well-documented source code, additional test reviews, integration test files.
- Submission archive: <GroupID>_DIC2025_Assignment_3.zip containing everything above.

-------------------------------------------------------------------------------

3. Environment and Tooling

3.1 Environment
- Python 3.11 (use pyenv for version management)
- Virtualenv for dependency isolation
- Docker/Docker Desktop (used to run LocalStack)
- LocalStack (AWS service emulator)

3.2 Utilities
- jq, zip (or tar on Windows), curl

3.3 Setup Steps
- Install Python 3.11 and pyenv/virtualenv
- Install Docker/Docker Desktop
- Install required utilities
- Install LocalStack and required Python packages
- Start LocalStack with debugging enabled
- Test awslocal CLI and connectivity

-------------------------------------------------------------------------------

4. Lambda Packaging and Dependencies

- Each Lambda must be zipped with its code and all required dependencies.
- Use pip install -t to a local “package” directory, then zip package/ and handler.py together.
- NLTK: Download and include all required corpora/data files in Lambda ZIP.
- Profanityfilter: Ensure all dependencies are included.
- Keep unzipped Lambda ZIPs under 250MB.
- Use the manylinux2014_x86_64 platform wheels for compatibility.
- Update function code by re-zipping and running awslocal lambda update-function-code.

-------------------------------------------------------------------------------

5. Event Routing and Chaining

- Direct S3 bucket notifications can only trigger a single Lambda.
- For more complex pipelines (multiple triggers), use EventBridge or SNS.
- Steps:
  - Configure S3 to send events to EventBridge.
  - Create EventBridge rules for desired event patterns.
  - Attach one or more Lambdas as targets to rules.
- Use CLI as shown in Tips_and_Tricks.pdf for setting up EventBridge rules.

-------------------------------------------------------------------------------

6. DynamoDB and State Tracking

- Use DynamoDB to count unpolite reviews per user and flag banned users.
- Use DynamoDB streams or event triggers to kick off banning logic if not done inside the profanity check Lambda.
- Each write to DynamoDB should be atomic and correctly increment counters.

-------------------------------------------------------------------------------

7. SSM Parameter Store Usage

- Store all resource names and important config (bucket names, table names) in SSM.
- Create SSM parameters during infra script setup.
- All Lambdas must read config from SSM at runtime.
- Do not hardcode any resource names in Lambda code.

-------------------------------------------------------------------------------

8. Testing

- Use pytest for all integration tests.
- Write tests to cover each step of the pipeline: preprocessing, profanity detection, sentiment analysis, banning.
- Use the provided tests/ folder in the tutorial as a template.
- Test pipeline repeatedly from a fresh LocalStack environment.

-------------------------------------------------------------------------------

9. Debugging and Troubleshooting

- Always run LocalStack in debug mode during development.
- Use LocalStack’s health check at http://localhost:4566/_localstack/health to verify service status.
- Check logs for silent failures or event misconfigurations.
- Keep a set of shell commands/scripts for common operations (upload/download S3, update Lambda code).

-------------------------------------------------------------------------------

10. Documentation and Reporting

- Report must follow provided structure and include architectural diagram (showing S3, Lambdas, EventBridge/SNS, DynamoDB, event flow).
- Instructions.pdf must detail every setup step, including environment prep, LocalStack/Docker, infra scripts, Lambda deployment, and testing.
- Document any “gotchas” (e.g., Lambda packaging issues, event routing pitfalls, LocalStack quirks).

-------------------------------------------------------------------------------

11. Workflow and Parallelization

11.1 Phased Approach (Top-Level)
- Environment Setup (parallel per team member)
- Project Initialization (git, structure, team roles)
- Infrastructure Scripting (can be parallelized: S3, DynamoDB, SSM, EventBridge/SNS)
- Lambda Function Development (each Lambda in parallel)
- Event Chaining and Integration (after infra/Lambdas)
- Dataset and Input Handling (can script in parallel)
- Integration Testing (starts once full pipeline runs, then parallelize test writing)
- Results Extraction and Verification
- Documentation and Reporting (some sections in parallel, results/conclusions last)
- Packaging and Submission (final step)

11.2 Dependencies
- Infra scripts must be ready before Lambdas can be deployed/integrated.
- Full event chaining tested only when all pipeline steps and infra are in place.
- Testing and documentation depend on working code and infra.

-------------------------------------------------------------------------------

12. Key Practical Tips and Pitfalls

- LocalStack environment is ephemeral: all resources must be created via script, not manually.
- Always package required NLTK data and dependencies into Lambda ZIP.
- Keep Lambda ZIPs under size limit.
- If pipeline requires multiple Lambdas to trigger on one event, set up EventBridge/SNS.
- Test Lambda SSM parameter reading: fetch config at runtime, not import time.
- Always test complete infrastructure creation, teardown, and redeployment (simulate a fresh LocalStack).
- Write and run integration tests early and often.
- Document every setup and debug step for teammates with no AWS experience.
- Use awslocal for all AWS CLI commands (never the vanilla aws CLI).
- Use health check and logs for debugging silent failures.
