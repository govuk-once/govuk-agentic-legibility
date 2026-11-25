# Alternative Frontends CDK Infrastructure

This directory contains the AWS CDK application responsible for deploying the infrastructure required to run the **alternative-frontends** application on AWS.

The infrastructure is intentionally separated from the SvelteKit application code so that platform resources can be managed independently of application releases.

---

## Architecture

The CDK application deploys:

- Amazon ECR repository
- Amazon ECS Fargate service
- Application Load Balancer (ALB)
- CloudWatch log group
- ECS IAM task role
- Amazon Polly permissions
- Amazon Transcribe permissions

The service is deployed into the default VPC in the target AWS account.

---

## Stack Layout

### AlternativeFrontendsRepositoryStack

Creates:

- ECR repository: `alternative-frontends`
- Lifecycle policy retaining the 10 most recent images

This stack changes rarely and is typically deployed once.

### AlternativeFrontendsServiceStack

Creates:

- ECS Cluster
- ECS Fargate Service
- Application Load Balancer
- CloudWatch Log Group
- ECS Task Role
- Polly and Transcribe permissions

This stack references the ECR repository and can be redeployed whenever infrastructure settings change.

---

## Directory Structure

```
cdk/
├── bin/
│   └── alternative-frontends.ts
├── lib/
│   ├── repository-stack.ts
│   └── service-stack.ts
├── package.json
├── tsconfig.json
├── cdk.json
└── README.md
```

---

## Prerequisites

Install the following:

- Node.js 22+
- AWS CLI v2
- AWS CDK v2

Verify access to the target AWS account:

```
aws sts get-caller-identity
```

Verify CDK installation:

```
npx cdk --version
```

---
## Environmental Variables

Provide a `.env` file containing the following:

```
CDK_DEFAULT_ACCOUNT=<your-account-number>
```

---

## Installation

From this directory:

```
npm install
```

Compile TypeScript:

```
npm run build
```

---

## CDK Bootstrap

CDK must be bootstrapped once per account and region.

Example:

```
npx cdk bootstrap aws://ACCOUNT_ID/eu-west-2
```

For example:

```
npx cdk bootstrap aws://123456789012/eu-west-2
```

---

## Deploy Repository Stack

Deploy the ECR repository first.

```
npx cdk deploy AlternativeFrontendsRepositoryStack
```

Expected resource:

```
alternative-frontends
```

The ECR repository URI will be displayed in the stack outputs.

---

## Build and Push Application Image

From the repository root:

```
docker build -t alternative-frontends .
```

Authenticate Docker with ECR:

```
aws ecr get-login-password \
  --region eu-west-2 \
| docker login \
  --username AWS \
  --password-stdin ACCOUNT_ID.dkr.ecr.eu-west-2.amazonaws.com
```

Tag the image:

```
docker tag alternative-frontends:latest \
ACCOUNT_ID.dkr.ecr.eu-west-2.amazonaws.com/alternative-frontends:latest
```

Push the image:

```
docker push \
ACCOUNT_ID.dkr.ecr.eu-west-2.amazonaws.com/alternative-frontends:latest
```

---

## Deploy Service Stack

After the image has been pushed:

```
npx cdk deploy AlternativeFrontendsServiceStack
```

Outputs include:

- Load balancer URL
- ECS cluster name
- ECS service name

---

## Deploy Everything

Deploy both stacks:

```
npx cdk deploy --all
```

---

## Update the Application

Build a new image:

```
docker build -t alternative-frontends .
```

Tag the image:

```
docker tag alternative-frontends:latest \
ACCOUNT_ID.dkr.ecr.eu-west-2.amazonaws.com/alternative-frontends:latest
```

Push the image:

```
docker push \
ACCOUNT_ID.dkr.ecr.eu-west-2.amazonaws.com/alternative-frontends:latest
```

Force ECS to pull and deploy the latest image:

```
aws ecs update-service \
  --cluster alternative-frontends \
  --service alternative-frontends \
  --force-new-deployment
```

No CDK deployment is required unless infrastructure has changed.

---

## Useful Commands

Generate CloudFormation templates:

```
npx cdk synth
```

Preview infrastructure changes:

```
npx cdk diff
```

Deploy the repository stack:

```
npx cdk deploy AlternativeFrontendsRepositoryStack
```

Deploy the service stack:

```
npx cdk deploy AlternativeFrontendsServiceStack
```

Deploy all stacks:

```
npx cdk deploy --all
```

Destroy the service stack:

```
npx cdk destroy AlternativeFrontendsServiceStack
```

Destroy the repository stack:

```
npx cdk destroy AlternativeFrontendsRepositoryStack
```

Destroy all stacks:

```
npx cdk destroy --all
```

---

## Notes

- The ECS service expects the application to listen on port `3000`.
- Health checks are configured against `/`.
- The ECS service uses the image tagged `latest`.
- The infrastructure currently uses the AWS account's default VPC.
- Container logs are written to CloudWatch Logs under:

```
/ecs/alternative-frontends
```

- The ECS task role includes Amazon Polly and Amazon Transcribe permissions for speech-related features.

---

## Future Improvements

Recommended next steps as the platform matures:

1. Create a dedicated VPC instead of using the default VPC.
2. Enable HTTPS using AWS Certificate Manager (ACM).
3. Add a Route 53 hosted zone and custom domain.
4. Move from the `latest` tag to immutable Git SHA image tags.
5. Add a GitHub Actions deployment workflow.
6. Store secrets in AWS Secrets Manager.
7. Add ECS autoscaling based on CPU and memory utilisation.
8. Enable AWS WAF on the Application Load Balancer.
