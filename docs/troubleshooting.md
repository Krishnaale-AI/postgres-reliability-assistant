# AI PostgreSQL DBA Health Assistant - Troubleshooting Guide

Common issues, root causes, and resolution steps for AWS RDS PostgreSQL, Bedrock, and pgvector.

---

### 1. Connection Error: `could not connect to server: Connection timed out`
- **Cause:** RDS Security Group is not allowing inbound TCP traffic on port 5432 from your current client public IP.
- **Resolution:**
  1. Open AWS RDS Console > Databases > `ai-postgres-dba` > Connectivity & security.
  2. Click the active VPC security group link.
  3. Edit inbound rules > Add rule:
     - Type: `PostgreSQL`
     - Port: `5432`
     - Source: `My IP` (Note: If your ISP rotates IP addresses, update this rule).

---

### 2. Error: `extension "vector" is not available`
- **Cause:** `pgvector` is available on RDS PostgreSQL 15, but you might be on an older minor version or an unsupported engine.
- **Resolution:**
  - Verify available extensions:
    ```sql
    SELECT * FROM pg_available_extensions WHERE name = 'vector';
    ```
  - Ensure your RDS instance is upgraded to PostgreSQL 15.2 or later (such as 15.16).

---

### 3. Bedrock Error: `AccessDeniedException` or `ResourceNotFoundException`
- **Cause:** IAM credentials lack permission to call Bedrock, or the model has not been enabled in the Bedrock Model Access console.
- **Resolution:**
  1. Open Bedrock Console > Model Access > Request access to **Amazon Nova Lite** and **Titan Text Embeddings**.
  2. Ensure your IAM policy includes:
     ```json
     {
       "Effect": "Allow",
       "Action": [
         "bedrock:InvokeModel",
         "bedrock:Converse"
       ],
       "Resource": "*"
     }
     ```

---

### 4. SSL Error: `SSL connection has been closed unexpectedly`
- **Cause:** Network proxy or firewall interfering with encrypted RDS traffic, or RDS certificate bundle missing.
- **Resolution:** Set `RDS_SSLMODE=prefer` or download the Amazon RDS Global Root CA certificate if using `verify-full`.

---

### 5. Running in Demo / Offline Mode
- If your AWS environment is not yet provisioned, you can still explore all dashboard tabs and features by setting in `.env`:
  ```ini
  DEMO_MODE=true
  ```
  or by toggling **"Simulate Demo Cluster Workload"** in the Streamlit sidebar.
