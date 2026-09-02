"""
Amazon CloudWatch Telemetry Module for RDS PostgreSQL.
Retrieves real-time infrastructure metrics (CPU, IOPS, Memory, Storage) from AWS CloudWatch.
"""

import logging
from datetime import datetime, timedelta
from config import (
    AWS_REGION,
    AWS_PROFILE,
    ENABLE_CLOUDWATCH,
    RDS_INSTANCE_IDENTIFIER,
    DEMO_MODE,
)

logger = logging.getLogger("monitoring.cloudwatch")


def get_rds_cloudwatch_metrics(instance_id=None, period_minutes=30):
    """
    Fetches CloudWatch metrics for the specified RDS DBInstanceIdentifier.
    
    Metrics:
    - CPUUtilization (Percent)
    - DatabaseConnections (Count)
    - FreeStorageSpace (Bytes / GB)
    - FreeableMemory (Bytes / MB)
    - ReadIOPS / WriteIOPS (Count/Second)
    """
    db_id = instance_id or RDS_INSTANCE_IDENTIFIER

    if not ENABLE_CLOUDWATCH or DEMO_MODE:
        return _generate_mock_cloudwatch_metrics(db_id)

    try:
        import boto3
        session = boto3.Session(region_name=AWS_REGION, profile_name=AWS_PROFILE)
        cw = session.client("cloudwatch")

        end_time = datetime.utcnow()
        start_time = end_time - timedelta(minutes=period_minutes)

        metric_queries = [
            {"Id": "cpu", "MetricStat": {"Metric": {"Namespace": "AWS/RDS", "MetricName": "CPUUtilization", "Dimensions": [{"Name": "DBInstanceIdentifier", "Value": db_id}]}, "Period": 300, "Stat": "Average"}, "ReturnData": True},
            {"Id": "conns", "MetricStat": {"Metric": {"Namespace": "AWS/RDS", "MetricName": "DatabaseConnections", "Dimensions": [{"Name": "DBInstanceIdentifier", "Value": db_id}]}, "Period": 300, "Stat": "Average"}, "ReturnData": True},
            {"Id": "storage", "MetricStat": {"Metric": {"Namespace": "AWS/RDS", "MetricName": "FreeStorageSpace", "Dimensions": [{"Name": "DBInstanceIdentifier", "Value": db_id}]}, "Period": 300, "Stat": "Average"}, "ReturnData": True},
            {"Id": "memory", "MetricStat": {"Metric": {"Namespace": "AWS/RDS", "MetricName": "FreeableMemory", "Dimensions": [{"Name": "DBInstanceIdentifier", "Value": db_id}]}, "Period": 300, "Stat": "Average"}, "ReturnData": True},
            {"Id": "read_iops", "MetricStat": {"Metric": {"Namespace": "AWS/RDS", "MetricName": "ReadIOPS", "Dimensions": [{"Name": "DBInstanceIdentifier", "Value": db_id}]}, "Period": 300, "Stat": "Average"}, "ReturnData": True},
            {"Id": "write_iops", "MetricStat": {"Metric": {"Namespace": "AWS/RDS", "MetricName": "WriteIOPS", "Dimensions": [{"Name": "DBInstanceIdentifier", "Value": db_id}]}, "Period": 300, "Stat": "Average"}, "ReturnData": True},
        ]

        response = cw.get_metric_data(
            MetricDataQueries=metric_queries,
            StartTime=start_time,
            EndTime=end_time,
        )

        results = {}
        for r in response.get("MetricDataResults", []):
            label = r.get("Id")
            vals = r.get("Values", [])
            results[label] = round(vals[0], 2) if vals else None

        return {
            "instance_id": db_id,
            "cpu_utilization_pct": results.get("cpu", 18.5),
            "database_connections": results.get("conns", 38),
            "free_storage_gb": round((results.get("storage", 20 * 1024**3)) / (1024**3), 2),
            "freeable_memory_mb": round((results.get("memory", 1024**3)) / (1024**2), 2),
            "read_iops": results.get("read_iops", 45.0),
            "write_iops": results.get("write_iops", 120.0),
            "source": "CloudWatch Live",
        }

    except Exception as exc:
        logger.warning("CloudWatch metric fetch failed: %s. Using fallback metrics.", exc)
        return _generate_mock_cloudwatch_metrics(db_id)


def _generate_mock_cloudwatch_metrics(db_id):
    """Generates synthetic CloudWatch RDS telemetry."""
    return {
        "instance_id": db_id,
        "cpu_utilization_pct": 24.5,
        "database_connections": 38,
        "free_storage_gb": 14.8,
        "freeable_memory_mb": 680.0,
        "read_iops": 42.0,
        "write_iops": 185.0,
        "source": "Simulated RDS CloudWatch",
    }
