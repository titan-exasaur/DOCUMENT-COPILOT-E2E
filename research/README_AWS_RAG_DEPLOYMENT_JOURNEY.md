# Document Co-Pilot — Local to AWS Deployment Journey

## Overview

This document captures the complete journey of deploying the **Document Co-Pilot RAG application** from a local machine to AWS cloud infrastructure.

The project evolved from a locally running Streamlit + RAG prototype into a deployed AI system running on AWS EC2 with Dockerized OpenSearch.

---

# Final Working Architecture

```text
User → Streamlit UI → Embedding Model → OpenSearch Vector DB → LLM Response
```

Deployed Components:

- AWS EC2
- Docker
- OpenSearch
- Streamlit
- Python Virtual Environment
- IAM Role-based Authentication
- GitHub Deployment Workflow

---

# Tech Stack Used

## Frontend / App Layer
- Streamlit

## AI / RAG Components
- SentenceTransformers
- OpenAI API
- Chunking Pipeline
- Vector Embeddings
- Semantic Retrieval

## Infrastructure
- AWS EC2
- AWS IAM
- AWS Security Groups
- Docker
- OpenSearch

## DevOps / Deployment
- GitHub
- SSH
- Linux
- systemd (planned)

---

# Step-by-Step Deployment Journey

---

# Step 1 — IAM Role Creation

Created an IAM role for the EC2 instance.

### Policies Attached

- AmazonS3FullAccess
- AmazonBedrockFullAccess
- AmazonOpenSearchServiceFullAccess
- CloudWatchAgentServerPolicy

### Why This Matters

Instead of storing AWS credentials manually inside the server:

```text
BAD → Hardcoded AWS keys
GOOD → IAM Role-based temporary credentials
```

This follows cloud-native security practices.

---

# Step 2 — Security Group Setup

Created a security group:

```text
document-copilot-sg
```

### Inbound Rules

| Type | Port | Purpose |
|------|------|----------|
| SSH | 22 | Server access |
| Custom TCP | 8501 | Streamlit app |

### Important Lesson

Using “My IP” for SSH is safer than opening SSH publicly.

---

# Step 3 — EC2 Launch

Initially attempted:

- Ubuntu 26.04
- Amazon Linux
- Ubuntu SQL AMIs accidentally

Finally used:

```text
Ubuntu Server 24.04 LTS
```

### Instance Configuration

| Component | Value |
|---|---|
| Instance Type | t3.medium |
| Storage | 20GB gp3 |
| Key Pair | RSA PEM |
| IAM Role | Attached |
| Security Group | Attached |

---

# Step 4 — SSH into EC2

Connected using:

```bash
ssh -i document-copilot-rsa.pem ubuntu@<public-ip>
```

### Important Learning

Ubuntu username:
```text
ubuntu
```

Amazon Linux username:
```text
ec2-user
```

---

# Step 5 — Python Environment Setup

Installed dependencies:

```bash
sudo apt update && sudo apt upgrade -y

sudo apt install -y python3 python3-venv python3-pip git
```

Created virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

---

# Step 6 — GitHub Deployment

Cloned repository directly into EC2:

```bash
git clone https://github.com/titan-exasaur/DOCUMENT-COPILOT-E2E.git .
```

Installed requirements:

```bash
pip install -r requirements.txt
```

---

# Step 7 — Environment Variables

Created `.env` manually on EC2 because:

```text
.env was ignored by GitHub (.gitignore)
```

Example:

```env
OPENAI_API_KEY="test"
AWS_REGION="us-east-1"
BUCKET_NAME="temp-bucket"
```

---

# Step 8 — AWS CLI Setup

Ubuntu 24.04 package issue:

```text
awscli package not available
```

### Solution

Installed AWS CLI manually:

```bash
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"

sudo ./aws/install
```

---

# Step 9 — First Successful Streamlit Deployment

Ran application:

```bash
streamlit run app.py --server.port 8501 --server.address 0.0.0.0
```

Accessed via:

```text
http://<public-ip>:8501
```

---

# Step 10 — OpenSearch Failure

Initial Error:

```text
Connection refused localhost:9200
```

Cause:
- OpenSearch server was not running

---

# Step 11 — Docker Installation

Installed Docker:

```bash
sudo apt install -y docker.io
```

Enabled Docker:

```bash
sudo systemctl enable docker
sudo systemctl start docker
```

---

# Step 12 — OpenSearch Docker Setup

Created Docker network:

```bash
docker network create opensearch-net
```

Initial OpenSearch container failed.

---

# Bugs Faced + Solutions

---

## Bug 1 — Python 3.11 Not Found

### Error

```text
Unable to locate package python3.11
```

### Cause

Wrong Ubuntu version / repository mismatch.

### Fix

Used:

```bash
sudo apt install -y python3 python3-venv python3-pip git
```

---

## Bug 2 — Wrong Ubuntu AMI

### Error

```text
Microsoft SQL Server is not supported for t3.medium
```

### Cause

Selected SQL-enabled Ubuntu image accidentally.

### Fix

Used clean Ubuntu 24.04 LTS AMI.

---

## Bug 3 — Missing .env Variables

### Error

```text
OpenAIError: Missing credentials
```

### Cause

`.env` not pushed to GitHub.

### Fix

Created `.env` manually on EC2.

---

## Bug 4 — OpenSearch Container Crash

### Error

```text
Container exited immediately
```

### Cause

Weak password + insufficient memory.

### Fix

Used:

```bash
OPENSEARCH_JAVA_OPTS=-Xms512m -Xmx512m
```

and strong password.

---

## Bug 5 — SSH Suddenly Stopped Working

### Cause

Laptop public IP changed after WiFi reconnect.

### Fix

Updated EC2 Security Group inbound SSH rule.

---

## Bug 6 — streamlit: command not found

### Cause

Virtual environment was not activated.

### Fix

```bash
source venv/bin/activate
```

---

# Final OpenSearch Working Command

```bash
docker run -d \
  --name opensearch-node \
  --network opensearch-net \
  -p 9200:9200 \
  -p 9600:9600 \
  -e "discovery.type=single-node" \
  -e "plugins.security.disabled=true" \
  -e "OPENSEARCH_JAVA_OPTS=-Xms512m -Xmx512m" \
  -e "OPENSEARCH_INITIAL_ADMIN_PASSWORD=StrongPass123!" \
  --ulimit memlock=-1:-1 \
  opensearchproject/opensearch:latest
```

Verification:

```bash
curl http://localhost:9200
```

---

# First Successful RAG Query

Example Query:

```text
what is androgenic alopecia
```

Successful Answer Generated from the uploaded document.

This confirmed:
- PDF parsing worked
- Chunking worked
- Embeddings worked
- Vector indexing worked
- Retrieval worked
- LLM generation worked

---

# Architectural Learnings

Moving from local → cloud exposed real-world issues:

- Latency
- Re-indexing overhead
- Streamlit rerun behavior
- Docker resource limits
- Networking
- Security Groups
- Vector DB setup
- Environment configuration
- Observability gaps

---

# Improvements Identified

## Immediate Improvements

### Streamlit Session State
Prevent re-indexing on every query.

### Logging
Add:
- embedding time
- retrieval time
- indexing time
- LLM response time

### Better UX
- loading indicators
- pipeline statuses
- source chunk visibility

---

# Planned AWS-Native Architecture

## Next Services Planned

### Amazon S3
Document storage.

### AWS Lambda
Async ingestion processing.

### AWS Step Functions
Pipeline orchestration.

### Amazon Bedrock
Replace OpenAI API.

### CloudWatch
Logging + observability.

---

# Cost Awareness

## Current Major Cost Source

### EC2 t3.medium
Approx:
```text
~$25–35/month if left running 24/7
```

### S3
Negligible for small usage.

### OpenSearch
Currently self-hosted inside EC2 via Docker.

---

# Recommended Cost Strategy

When not actively using:

```text
STOP the EC2 instance
```

Do NOT terminate.

Stopping preserves:
- code
- Docker
- EBS storage
- configuration

while significantly reducing costs.

---

# Current System Status

## Successfully Working

- EC2 deployment
- SSH access
- Streamlit UI
- PDF upload
- Chunking pipeline
- Embeddings
- OpenSearch vector DB
- Semantic retrieval
- LLM responses
- Docker infrastructure

---

# Key Engineering Takeaway

The biggest learning was understanding the difference between:

```text
"ML code that runs locally"
```

vs

```text
"AI systems that operate on real infrastructure"
```

This project introduced practical exposure to:
- cloud deployment
- infrastructure debugging
- vector databases
- Docker
- networking
- observability
- deployment workflows
- runtime operations

---

# Author

Amith Kumar S

Applied AI / ML Engineering Journey
