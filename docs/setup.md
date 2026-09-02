# Step-by-Step Setup Guide: AWS RDS PostgreSQL 15.16 & Bedrock

This guide walks through deploying the **AI PostgreSQL DBA Assistant** on AWS RDS PostgreSQL 15.16 and configuring Amazon Bedrock.

---

## Phase 1: Create AWS RDS PostgreSQL 15.16 Instance

1. Open the [Amazon RDS Console](https://console.aws.amazon.com/rds/).
2. Select your desired AWS Region (e.g. `us-east-1`).
3. Click **Create database**:
   - **Method:** Standard create
   - **Engine type:** PostgreSQL
   - **Engine Version:** PostgreSQL 15.16 (or latest 15.x minor version)
   - **Templates:** Free tier (or Dev/Test)
   - **DB instance identifier:** `ai-postgres-dba`
   - **Master username:** `postgres`
   - **Credentials:** Manage master credentials in AWS Secrets Manager (recommended) or specify master password.
   - **Instance configuration:** `db.t3.micro` or `db.t4g.micro`
   - **Storage:** General Purpose SSD (gp3 / gp2), 20 GiB
   - **Connectivity:**
     - VPC: Default VPC
     - Public access: Yes (for local development lab)
     - Security Group: Create new (`ai-postgres-dba-sg`), allow Inbound PostgreSQL (Port 5432) from **My IP**
   - **Additional Configuration:**
     - Initial database name: `dba_ai`
     - DB parameter group: Default or custom parameter group with `shared_preload_libraries = pg_stat_statements`

---

## Phase 2: Enable PostgreSQL Extensions & Initialize Schema

Connect to your database via `psql`:

```powershell
psql -h ai-postgres-dba.xxxxxxxxx.us-east-1.rds.amazonaws.com -p 5432 -U postgres -d dba_ai
```

Execute the database initialization script:

```sql
\i sql/setup.sql
```

Verify extensions:
```sql
SELECT extname, extversion FROM pg_extension WHERE extname IN ('pg_stat_statements', 'vector');
```

---

## Phase 3: Configure AWS Credentials & Amazon Bedrock

1. Configure AWS CLI:
   ```powershell
   aws configure
   ```
2. In the [Amazon Bedrock Console](https://console.aws.amazon.com/bedrock/), ensure model access is enabled for:
   - **Amazon Nova Lite** (`amazon.nova-lite-v1:0`)
   - **Amazon Titan Text Embeddings V2** (`amazon.titan-embed-text-v2:0`)

---

## Phase 4: Local Python Environment Setup

1. Create and activate a virtual environment:
   ```powershell
   py -3.12 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```

3. Configure `.env`:
   ```powershell
   copy .env.example .env
   ```
   Edit `.env` with your RDS endpoint, credentials, and region.

---

## Phase 5: Run Diagnostics & Launch Dashboard

1. Test database connectivity:
   ```powershell
   python test_connection.py
   ```

2. Test Amazon Bedrock & pgvector:
   ```powershell
   python test_bedrock.py
   ```

3. Launch the Streamlit dashboard:
   ```powershell
   streamlit run app.py
   ```
   Open your browser at `http://localhost:8501`.
