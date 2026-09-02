"""
Configuration module for the AI PostgreSQL DBA Health Assistant.
Handles environment variables and optional AWS Secrets Manager credential resolution.
"""

import json
import os
import logging
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

# Configure basic logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("config")

# Load environment variables from .env file if present
load_dotenv()

# AWS Configuration
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
AWS_PROFILE = os.getenv("AWS_PROFILE", None)

# Secrets Manager Settings
USE_SECRETS_MANAGER = os.getenv("USE_SECRETS_MANAGER", "false").lower() in ("true", "1", "yes")
RDS_SECRET_NAME = os.getenv("RDS_SECRET_NAME", "postgres-dba-ai-secret")

# Database Connection Settings
RDS_HOST = os.getenv("RDS_HOST", "localhost")
RDS_PORT = int(os.getenv("RDS_PORT", "5432"))
RDS_DATABASE = os.getenv("RDS_DATABASE", "dba_ai")
RDS_USER = os.getenv("RDS_USER", "postgres")
RDS_PASSWORD = os.getenv("RDS_PASSWORD", "")
RDS_SSLMODE = os.getenv("RDS_SSLMODE", "prefer")  # Use 'require' for RDS
RDS_INSTANCE_IDENTIFIER = os.getenv("RDS_INSTANCE_IDENTIFIER", "ai-postgres-dba")

# Bedrock Model Configuration
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "amazon.nova-lite-v1:0")
BEDROCK_EMBEDDING_MODEL_ID = os.getenv("BEDROCK_EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v2:0")
EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "1024"))

# CloudWatch & Simulation
ENABLE_CLOUDWATCH = os.getenv("ENABLE_CLOUDWATCH", "true").lower() in ("true", "1", "yes")
DEMO_MODE = os.getenv("DEMO_MODE", "false").lower() in ("true", "1", "yes")


def resolve_db_credentials():
    """
    Resolves database credentials from AWS Secrets Manager if configured,
    otherwise returns the environment variable settings.
    """
    global RDS_HOST, RDS_PORT, RDS_DATABASE, RDS_USER, RDS_PASSWORD

    if USE_SECRETS_MANAGER:
        try:
            import boto3
            from botocore.exceptions import ClientError

            session = boto3.Session(region_name=AWS_REGION, profile_name=AWS_PROFILE)
            client = session.client("secretsmanager")
            logger.info("Fetching database credentials from Secrets Manager: %s", RDS_SECRET_NAME)
            response = client.get_secret_value(SecretId=RDS_SECRET_NAME)

            if "SecretString" in response:
                secret = json.loads(response["SecretString"])
                RDS_HOST = secret.get("host", RDS_HOST)
                RDS_PORT = int(secret.get("port", RDS_PORT))
                RDS_DATABASE = secret.get("dbname", secret.get("database", RDS_DATABASE))
                RDS_USER = secret.get("username", secret.get("user", RDS_USER))
                RDS_PASSWORD = secret.get("password", RDS_PASSWORD)
                logger.info("Successfully loaded database credentials from AWS Secrets Manager")
            else:
                logger.warning("SecretString not found in Secrets Manager response.")
        except Exception as err:
            logger.error("Failed to load credentials from Secrets Manager (%s). Falling back to .env settings.", err)

    return {
        "host": RDS_HOST,
        "port": RDS_PORT,
        "database": RDS_DATABASE,
        "user": RDS_USER,
        "password": RDS_PASSWORD,
        "sslmode": RDS_SSLMODE,
    }


# Initial resolution on module import
_db_creds = resolve_db_credentials()
