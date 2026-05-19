# 📄 Document Co-Pilot — AWS Migration Journal

> Cloud-Native RAG Pipeline: from local prototype to AWS-native architecture.
> Built session by session. Every bug logged. Every fix documented.

---

## Table of Contents

- [Project Overview](#project-overview)
- [Architecture](#architecture)
- [What Was Built Locally (Before Migration)](#what-was-built-locally-before-migration)
- [Migration Steps](#migration-steps)
  - [Step 1 — EC2 Deployment](#step-1--ec2-deployment)
  - [Step 2 — S3 Integration](#step-2--s3-integration)
  - [Step 3 — Lambda Ingestion Pipeline](#step-3--lambda-ingestion-pipeline)
- [Bug Log](#bug-log)
- [Key Architectural Decisions](#key-architectural-decisions)
- [Remaining Steps](#remaining-steps)
- [Environment Variables Reference](#environment-variables-reference)
- [How to Resume This Project](#how-to-resume-this-project)

---

## Project Overview

A RAG (Retrieval-Augmented Generation) Document Co-Pilot that allows users to upload PDFs and ask questions about them. Started as a fully local pipeline and is being migrated to AWS cloud-native architecture incrementally.

**Repo:** https://github.com/titan-exasaur/DOCUMENT-COPILOT-E2E

---

## Architecture

### Target AWS Architecture

```
User uploads PDF
      ↓
Streamlit UI (EC2)
      ↓
S3 Bucket (stores raw PDF)
      ↓
S3 Event → Lambda trigger (s3:PutObject on *.pdf)
      ↓
Lambda function:
    1. Download PDF from S3 to /tmp
    2. Extract text (PyPDF)
    3. Chunk text (overlap strategy)
    4. Embed chunks (OpenAI text-embedding-3-small, 1536-dim)
    5. Index into AWS OpenSearch
      ↓
User asks question
      ↓
Streamlit embeds query (OpenAI text-embedding-3-small)
      ↓
OpenSearch kNN retrieval (top-k chunks, filtered by doc_hash)
      ↓
Prompt + context → OpenAI LLM
      ↓
Answer displayed in UI
      ↓
Metadata logged to MongoDB Atlas
```

### Key Design Principle

**Streamlit is now a pure frontend.** All heavy lifting (extraction, chunking, embedding, indexing) happens in Lambda asynchronously after S3 upload. Streamlit only handles upload and query.

---

## What Was Built Locally (Before Migration)

| Component | Local Implementation |
|---|---|
| UI | Streamlit |
| PDF ingestion | PyPDF |
| Chunking | Custom overlap chunker |
| Embeddings | SentenceTransformers `all-MiniLM-L6-v2` (384-dim) |
| Vector DB | Local Docker OpenSearch |
| LLM | OpenAI API |
| Retrieval | Semantic kNN search |

### Local Pipeline Flow

```
Upload PDF → Extract → Chunk → Embed (local model) → Index → Query → Retrieve → Generate → Display
```

Everything ran inside Streamlit. No separation of concerns.

---

## Migration Steps

### Step 1 — EC2 Deployment

**Goal:** Host Streamlit app on AWS EC2 instead of running locally.

**What was done:**

1. Created IAM role `document-copilot-ec2-role` with policies:
   - `AmazonS3FullAccess`
   - `AmazonBedrockFullAccess`
   - `AmazonOpenSearchServiceFullAccess`
   - `CloudWatchAgentServerPolicy`

2. Created Security Group `document-copilot-sg`:
   - SSH port 22 — restricted to your IP only
   - TCP port 8501 — open (Streamlit)

3. Launched EC2:
   - AMI: Ubuntu Server 22.04 LTS
   - Instance type: `t3.medium` (2 vCPU, 4GB RAM)
   - Storage: 20GB gp3

4. SSH setup:
   ```bash
   chmod 400 ~/Downloads/your-key.pem
   ssh -i ~/Downloads/your-key.pem ubuntu@<public-ip>
   ```

5. Server setup:
   ```bash
   sudo apt update && sudo apt upgrade -y
   sudo apt install -y python3.11 python3.11-venv python3-pip git
   mkdir -p ~/app && cd ~/app
   git clone https://github.com/titan-exasaur/DOCUMENT-COPILOT-E2E.git .
   python3.11 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

6. Ran app manually first to verify:
   ```bash
   streamlit run app.py --server.port 8501 --server.address 0.0.0.0
   ```

**Status:** ✅ Complete

---

### Step 2 — S3 Integration

**Goal:** Upload PDFs to S3 instead of processing them locally in Streamlit.

**What was done:**

1. Created S3 bucket `document-copilot-s3-bucket` in `us-east-1`

2. Updated `app.py` to upload PDF to S3 via boto3:
   ```python
   s3_client.put_object(
       Bucket=S3_BUCKET_NAME,
       Key=s3_filename,
       Body=pdf_bytes,
       ContentType="application/pdf",
       Metadata={"doc_hash": pdf_hash, "upload_time": upload_time}
   )
   ```

3. Added session state caching with MD5 hash to avoid re-uploading same PDF:
   ```python
   pdf_hash = hashlib.md5(pdf_bytes).hexdigest()
   if st.session_state.processed_pdf_hash != pdf_hash:
       # upload
   ```

4. Removed all local processing from `app.py`:
   - Removed SentenceTransformers model loading
   - Removed local chunking/embedding/indexing
   - Removed batch_embed(), model caching, chunk caching

5. Added `src/query_embedding.py` using OpenAI API (replaces local model for queries):
   ```python
   def embed_query(query, client):
       response = client.embeddings.create(
           model="text-embedding-3-small",
           input=query
       )
       return response.data[0].embedding
   ```

**Status:** ✅ Complete

**Critical architectural insight:** Ingestion and retrieval must use the **same embedding model**. We switched both Lambda (ingestion) and Streamlit (query) to `text-embedding-3-small` (1536-dim). Mixing models = garbage retrieval.

---

### Step 3 — Lambda Ingestion Pipeline

**Goal:** Automatically process PDFs when they land in S3, with no Streamlit involvement.

**Lambda function:** `document-copilot-ingestion`
- Runtime: Python 3.12
- Memory: 512MB
- Timeout: 5 minutes
- Trigger: S3 PUT on `*.pdf` files

**What was done:**

1. Created Lambda deployment package in `~/lambda_package/`

2. Added new functions to existing src modules (without breaking existing ones):

   **`src/document_loader.py`** — added `load_pdf_from_bytes(pdf_bytes)`:
   ```python
   def load_pdf_from_bytes(pdf_bytes: bytes) -> str:
       reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
       text = ""
       for page in reader.pages:
           page_text = page.extract_text()
           if page_text:
               text += page_text + "\n"
       return text
   ```

   **`src/embeddings.py`** — added `embed_chunks_api(chunks, client)`:
   ```python
   def embed_chunks_api(chunks: List[str], client) -> List[List[float]]:
       response = client.embeddings.create(
           model="text-embedding-3-small",
           input=chunks
       )
       return [item.embedding for item in response.data]
   ```

   **`src/document_indexing.py`** — new file with `index_documents_with_hash()`:
   ```python
   def index_documents_with_hash(client, chunks, embeddings, doc_hash, source_key):
       for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
           doc = {
               "text": chunk,
               "embedding": embedding,
               "doc_hash": doc_hash,    # ← fixes chunk contamination (BUG-03)
               "source_key": source_key,
               "chunk_index": i
           }
           client.index(index="document-copilot-index", body=doc)
   ```

3. Packaged Lambda:
   ```bash
   cd ~/lambda_package
   pip install pypdf openai boto3 opensearch-py python-dotenv -t .
   find . -type d -name "__pycache__" -exec rm -rf {} +
   # ZIP from inside the folder — critical for correct root structure
   cd ~
   zip -r lambda_deployment.zip lambda_package/
   # Then rezip from inside:
   cd ~/lambda_package
   zip -r ~/lambda_deployment.zip .
   aws s3 cp ~/lambda_deployment.zip s3://document-copilot-s3-bucket/lambda/lambda_deployment.zip
   ```

4. Deployed to Lambda via S3 URL, set handler to `lambda_function.handler`

5. Added S3 trigger: PUT events, suffix `.pdf`

6. Recreated OpenSearch index with correct 1536 dimensions:
   ```bash
   curl -X DELETE "https://<opensearch-endpoint>/document-copilot-index" -u 'admin:password'
   curl -X PUT "https://<opensearch-endpoint>/document-copilot-index" \
     -u 'admin:password' \
     -H "Content-Type: application/json" \
     -d '{"settings":{"index":{"knn":true}},"mappings":{"properties":{"text":{"type":"text"},"embedding":{"type":"knn_vector","dimension":1536},"doc_hash":{"type":"keyword"},"source_key":{"type":"keyword"},"chunk_index":{"type":"integer"}}}}'
   ```

7. Fixed `config.py`:
   ```python
   INDEX_NAME = "document-copilot-index"   # was "document-index"
   EMBEDDING_DIM = 1536                     # was 384
   ```

**Status:** ✅ Complete — end-to-end pipeline verified working.

---

## Bug Log

### BUG-01 — Scanned PDF degraded extraction
**Status:** Known, parked  
**Symptom:** Scanned PDFs return empty or near-empty text. PyPDF can only extract text from text-based PDFs, not image-based scans.  
**Root cause:** No OCR layer in the pipeline.  
**Lambda handling:** Returns `statusCode: 422` with message "Scanned PDF - Textract needed" if extracted text < 50 characters.  
**Fix (future):** Integrate AWS Textract for OCR on scanned documents.

---

### BUG-02 — Short document poor retrieval (e.g. resumes)
**Status:** Known, parked  
**Symptom:** Resumes and short documents produce very few chunks, retrieval returns thin context, LLM gives vague answers.  
**Root cause:** Chunking strategy not optimized for short documents. Fixed chunk size produces too few chunks below top-k threshold.  
**Fix (future):** Adaptive chunking — smaller chunk size and overlap for short documents, detect document length before chunking.

---

### BUG-03 — Stale chunk contamination across sessions
**Status:** ✅ Fixed  
**Symptom:** Querying a new document returned chunks from previously uploaded documents.  
**Root cause:** OpenSearch index had no per-document filtering. All chunks from all documents mixed together.  
**Fix:** Added `doc_hash` field to every indexed document. Retrieval query now filters by `doc_hash`:
```python
"filter": [{"term": {"doc_hash": doc_hash}}]
```
This scopes retrieval to only the current document's chunks.

---

### BUG-04 — Page reload required occasionally
**Status:** Known, parked  
**Symptom:** Streamlit UI occasionally gets into inconsistent state mid-flow, requires full page reload.  
**Root cause:** `st.session_state` desync — session state variables get out of sync during error paths.  
**Fix (future):** Add explicit state reset guard at top of main flow. Reset all session state keys when a new PDF is detected.

---

### BUG-05 — Lambda zip structure wrong
**Status:** ✅ Fixed  
**Symptom:** `Runtime.HandlerNotFound: Handler 'handler' missing on module 'lambda_function'`  
**Root cause:** Zipped from parent directory — created `lambda_package/lambda_function.py` instead of `lambda_function.py` at root.  
**Fix:** Always zip from **inside** the package folder:
```bash
cd ~/lambda_package
zip -r ~/lambda_deployment.zip .   # NOT: zip -r deployment.zip lambda_package/
```

---

### BUG-06 — Lambda package too large (262MB limit exceeded)
**Status:** ✅ Fixed  
**Symptom:** `Unzipped size must be smaller than 262144000 bytes`  
**Root cause:** AWS CLI installer directory (`aws/`) accidentally left inside `lambda_package/` after installing AWS CLI. Also included `boto3`/`botocore` unnecessarily.  
**Fix:**
```bash
rm -rf ~/lambda_package/aws          # AWS CLI installer — 258MB
rm -rf ~/lambda_package/boto3        # Lambda runtime already has boto3
rm -rf ~/lambda_package/botocore
rm -rf ~/lambda_package/s3transfer
```
Final size: 80MB zipped, 110MB unzipped.

---

### BUG-07 — Unicode corruption in Python files (U+0302)
**Status:** ✅ Fixed  
**Symptom:** `Runtime.UserCodeSyntaxError: invalid character '̂' (U+0302) (embeddings.py, line 1)`  
**Root cause:** `nano` editor introduced invisible unicode character at the start of files during editing sessions.  
**Detection:**
```bash
xxd ~/lambda_package/src/embeddings.py | head -3
# Corrupt: 00000000: cc82 696d 706f 7274  (cc82 = U+0302)
# Clean:   00000000: 696d 706f 7274 206f  (starts with "import")
```
**Fix:** Rewrote affected files using `cat > file << 'EOF'` heredoc instead of nano. Never use nano for these files again — use `cat >` or write from local machine and SCP.

---

### BUG-08 — Embedding dimension mismatch (384 vs 1536)
**Status:** ✅ Fixed  
**Symptom:** `Query vector has invalid dimension: 1536. Dimension should be: 384`  
**Root cause:** OpenSearch index was created with 384 dimensions (SentenceTransformers era). Lambda now indexes with OpenAI embeddings (1536-dim). Query also produces 1536-dim vectors.  
**Fix:**
1. Deleted old index
2. Recreated with `"dimension": 1536`
3. Fixed `config.py`: `EMBEDDING_DIM = 1536`, `INDEX_NAME = "document-copilot-index"`

---

### BUG-09 — OpenSearch wrong index name
**Status:** ✅ Fixed  
**Symptom:** Retrieval hitting wrong index, no results.  
**Root cause:** `config.py` had `INDEX_NAME = "document-index"` (missing `-copilot`). Index in OpenSearch was named `document-copilot-index`.  
**Fix:** Updated `config.py` to `INDEX_NAME = "document-copilot-index"`.

---

### BUG-10 — `store_metadata()` signature mismatch
**Status:** ✅ Fixed (workaround)  
**Symptom:** `store_metadata() missing 5 required positional arguments: 'document_processing_time', 'document_embedding_time', 'chunk_count', 'embedding_count', 'indexing_time'`  
**Root cause:** `mongodb_handler.py` was written for the local pipeline where Streamlit did everything and had all timing data. After migration, Lambda does ingestion so Streamlit no longer has those timings.  
**Fix:** Pass `None` for Lambda-side fields from Streamlit. Lambda will log its own metadata to MongoDB in a future step.

---

### BUG-11 — IAM user missing S3 permissions
**Status:** ✅ Fixed  
**Symptom:** `AccessDenied when calling PutObject: user document-copilot-opensearch-user is not authorized`  
**Root cause:** App was using IAM user credentials (from `.env`) that only had OpenSearch permissions, not S3.  
**Fix:** Added `AmazonS3FullAccess` to `document-copilot-opensearch-user` in IAM.  
**Long-term fix (pending):** Remove hardcoded IAM user credentials, use EC2 instance role exclusively.

---

### BUG-12 — `.env` file empty after SSH session restart
**Status:** ✅ Fixed  
**Symptom:** All env var calls returning `None`, connections failing silently.  
**Root cause:** `.env` file was present but empty — credentials had not been written to the EC2 instance.  
**Fix:** Recreated `.env` with all required values using `nano ~/app/.env`.

---

## Key Architectural Decisions

### Why OpenAI embeddings instead of SentenceTransformers in Lambda?

SentenceTransformers model (`all-MiniLM-L6-v2`) is ~90MB with heavy dependencies. Lambda has a 250MB unzipped package limit. Using the OpenAI embeddings API has zero size cost and no model loading time.

**Trade-off:** API call latency + cost per embedding. Acceptable for this scale.

### Why store `doc_hash` on every chunk?

Prevents cross-document contamination (BUG-03). When user uploads Document B, their queries should only retrieve chunks from Document B, not Document A they uploaded earlier. `doc_hash` is an MD5 of the raw PDF bytes — unique per file.

### Why not Step Functions yet?

Lambda directly runs the full pipeline for now. Step Functions adds retry logic, state tracking, and parallel execution — useful at scale but unnecessary for a learning project. Added later once Lambda pipeline is stable.

### Why `boto3` is excluded from the Lambda package?

Lambda runtime already includes `boto3` and `botocore`. Including them in your package adds ~30MB for no reason and can cause version conflicts.

---

## Remaining Steps

| Step | Description | Status |
|---|---|---|
| Step 4 | Bedrock integration — replace OpenAI LLM with Claude | Pending |
| Step 5 | Step Functions — wrap Lambda in state machine | Pending |
| Step 6 | systemd service — Streamlit survives EC2 reboots | Pending |
| Step 7 | Lambda logs metadata to MongoDB directly | Pending |
| Step 8 | Textract — fix BUG-01 scanned PDFs | Pending |
| Step 9 | CloudWatch dashboards — monitoring | Pending |

---

## Environment Variables Reference

```bash
# OpenAI
OPENAI_API_KEY=

# MongoDB Atlas
MONGO_DB_USERNAME=
MONGO_DB_PASSWORD=
MONGO_CONNECTION_URI=

# AWS OpenSearch
OPENSEARCH_USERNAME=
OPENSEARCH_PASSWORD=
OPENSEARCH_HOST=           # full https:// URL

# AWS (only needed if not using instance role)
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=us-east-1
```

---

## How to Resume This Project

### Start EC2
1. Go to EC2 → Instances → Start instance
2. Note the new public IP (changes on restart unless you assign an Elastic IP)
3. SSH in: `ssh -i document-copilot-rsa.pem ubuntu@<new-ip>`

### Start the app
```bash
cd ~/app
source venv/bin/activate
streamlit run app.py --server.port 8501 --server.address 0.0.0.0
```

### Recreate OpenSearch domain
After creating a new domain, update:
1. `~/app/.env` — new `OPENSEARCH_HOST`, credentials
2. Lambda env vars — same values
3. Recreate index with dimension 1536:
```bash
curl -X PUT "https://<new-endpoint>/document-copilot-index" \
  -u 'admin:password' \
  -H "Content-Type: application/json" \
  -d '{"settings":{"index":{"knn":true}},"mappings":{"properties":{"text":{"type":"text"},"embedding":{"type":"knn_vector","dimension":1536},"doc_hash":{"type":"keyword"},"source_key":{"type":"keyword"},"chunk_index":{"type":"integer"}}}}'
```

### Update Lambda if code changed
```bash
cd ~/lambda_package
rm -rf src
cp -r ~/app/src ./src
cd ~
rm lambda_deployment.zip
cd ~/lambda_package
zip -r ~/lambda_deployment.zip .
aws s3 cp ~/lambda_deployment.zip s3://document-copilot-s3-bucket/lambda/lambda_deployment.zip
# Then in Lambda console: Code → Upload from S3 → save
```

---

*Last updated: May 2026 — after Session 1 of AWS migration.*
