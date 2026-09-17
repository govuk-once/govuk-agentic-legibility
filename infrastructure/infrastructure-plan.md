# Infrastructure Deployment Plan

## Overview

This document describes the target AWS infrastructure architecture for the Agentic Legibility platform, including the existing services and the planned deployment of Temporal to support durable workflow execution. The goal is to move all core services into AWS so that developers no longer need to run Temporal, workers, or the durable interpreter locally.

---

# Objectives

The infrastructure should:

- Run all application components within AWS.
- Provide durable workflow execution using Temporal.
- Use managed AWS services where possible.
- Support secure internal communication between services.
- Minimise operational overhead.
- Allow independent deployment of services.
- Support future scaling requirements.

---

# Infrastructure Components

## Shared VPC Stack (Existing)

Provides a common networking layer used by all application services.
A shared VPC allows all services to communicate privately while still enabling controlled access to public-facing endpoints.

### AWS Services

- VPC
- Private subnets
- Public subnets
- Route tables
- Internet Gateway
- NAT Gateway

---

## Token Secrets Stack (Existing)

Stores application secrets and credentials. Avoids storing credentials within source code or deployment configurations.

### AWS Services

- AWS Secrets Manager

---

## Workflow Server Stack (Existing)

Hosts the workflow definiton server.

### AWS Services

- ECS Fargate
- Application Load Balancer
- CloudWatch Logs

---

## Mock Server Stack (Existing)

Provides stub endpoint implementations of external integrations.

### AWS Services

- ECS Fargate
- Application Load Balancer
- CloudWatch Logs

---

## Temporal Database Stack (Existing)

Temporal requires durable storage for:

- Workflow state
- Activity state
- Workflow history
- Task queues
- Retry information

Without persistent storage, workflow execution would be lost when the server restarts.

```text
Temporal Server
        │
        ▼
RDS PostgreSQL
```
The PostgreSQL database:

- Is not publicly accessible.
- Is deployed into private subnets.
- Uses encrypted storage.
- Stores credentials in Secrets Manager.

Current ingress configuration allows access from within the VPC.

```text
VPC CIDR
    │
    ▼
PostgreSQL :5432
```

### AWS Services

- Amazon RDS PostgreSQL
- Security Groups
- AWS Secrets Manager

### Configuration

Current implementation:

- PostgreSQL 16
- Single AZ
- 20 GB storage
- Storage encryption enabled
- Daily backups retained for 7 days
- Private subnets only

---

## Temporal Server Stack (In Progress)

### Purpose

Hosts the Temporal control plane, which:

- Accepts workflow execution requests.
- Schedules workflow tasks.
- Coordinates workers.
- Persists workflow state to PostgreSQL.

### AWS Services

- ECS Fargate
- Internal Application Load Balancer
- CloudWatch Logs

### Container Image

```text
temporalio/auto-setup
```
---

## Temporal Worker Stack (Planned)

- Poll Temporal task queues.
- Execute activities.
- Report results back to Temporal.

```text
Worker
    │
    ▼
Temporal Server
```

### AWS Services

- ECS Fargate
- CloudWatch Logs

---

## Durable Interpreter Stack (Planned)

### Purpose

Hosts the durable workflow interpreter which:

- Communicates with Temporal workers.
- Executes workflow defintions.
- Manages workflow state.

```text
Interpreter
    │
    ▼
Temporal Server
```

### AWS Services

- ECS Fargate
- CloudWatch Logs

---

# Deployment Order

The recommended deployment order is:

```text
1. TemporalDatabaseStack
2. TemporalServerStack
3. TemporalWorkerStack
4. DurableInterpreterStack
```
