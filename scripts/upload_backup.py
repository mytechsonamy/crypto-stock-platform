#!/usr/bin/env python3
"""
Offsite Backup Upload Script
Uploads database backups to cloud storage (AWS S3 or Google Cloud Storage)
"""

import os
import sys
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from loguru import logger
import boto3
from botocore.exceptions import ClientError, NoCredentialsError


def setup_logging(verbose: bool = False):
    """Setup logging configuration"""
    logger.remove()
    level = "DEBUG" if verbose else "INFO"
    logger.add(sys.stderr, level=level)
    logger.add("logs/backup_upload_{time}.log", rotation="1 day", retention="30 days")


def upload_to_s3(backup_file: Path, bucket: str, prefix: str = 'backups') -> str:
    """
    Upload backup to AWS S3
    
    Args:
        backup_file: Path to backup file
        bucket: S3 bucket name
        prefix: S3 key prefix
        
    Returns:
        S3 URI of uploaded file
    """
    try:
        s3_client = boto3.client('s3')
        
        # Generate S3 key
        timestamp = datetime.now().strftime("%Y/%m/%d")
        s3_key = f"{prefix}/{timestamp}/{backup_file.name}"
        
        logger.info(f"Uploading to S3: s3://{bucket}/{s3_key}")
        
        # Upload with progress
        file_size = backup_file.stat().st_size
        logger.info(f"File size: {file_size / 1024 / 1024:.2f} MB")
        
        s3_client.upload_file(
            str(backup_file),
            bucket,
            s3_key,
            ExtraArgs={
                'StorageClass': 'STANDARD_IA',  # Infrequent Access for cost savings
                'ServerSideEncryption': 'AES256'
            }
        )
        
        s3_uri = f"s3://{bucket}/{s3_key}"
        logger.success(f"Upload completed: {s3_uri}")
        
        return s3_uri
        
    except NoCredentialsError:
        logger.error("AWS credentials not found")
        raise
    except ClientError as e:
        logger.error(f"S3 upload failed: {e}")
        raise
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise


def upload_to_gcs(backup_file: Path, bucket: str, prefix: str = 'backups') -> str:
    """
    Upload backup to Google Cloud Storage
    
    Args:
        backup_file: Path to backup file
        bucket: GCS bucket name
        prefix: GCS object prefix
        
    Returns:
        GCS URI of uploaded file
    """
    try:
        from google.cloud import storage
        
        storage_client = storage.Client()
        bucket_obj = storage_client.bucket(bucket)
        
        # Generate GCS object name
        timestamp = datetime.now().strftime("%Y/%m/%d")
        blob_name = f"{prefix}/{timestamp}/{backup_file.name}"
        
        logger.info(f"Uploading to GCS: gs://{bucket}/{blob_name}")
        
        # Upload
        blob = bucket_obj.blob(blob_name)
        blob.upload_from_filename(str(backup_file))
        
        gcs_uri = f"gs://{bucket}/{blob_name}"
        logger.success(f"Upload completed: {gcs_uri}")
        
        return gcs_uri
        
    except Exception as e:
        logger.error(f"GCS upload failed: {e}")
        raise


def cleanup_old_backups_s3(bucket: str, prefix: str, retention_days: int):
    """
    Delete old backups from S3 based on retention policy
    
    Args:
        bucket: S3 bucket name
        prefix: S3 key prefix
        retention_days: Number of days to retain backups
    """
    try:
        s3_client = boto3.client('s3')
        
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        logger.info(f"Cleaning up backups older than {cutoff_date.date()}")
        
        # List objects
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=bucket, Prefix=prefix)
        
        deleted_count = 0
        for page in pages:
            if 'Contents' not in page:
                continue
                
            for obj in page['Contents']:
                if obj['LastModified'].replace(tzinfo=None) < cutoff_date:
                    logger.debug(f"Deleting old backup: {obj['Key']}")
                    s3_client.delete_object(Bucket=bucket, Key=obj['Key'])
                    deleted_count += 1
        
        if deleted_count > 0:
            logger.info(f"Deleted {deleted_count} old backups")
        else:
            logger.info("No old backups to delete")
            
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        # Don't raise - cleanup failure shouldn't fail the upload


def cleanup_old_backups_gcs(bucket: str, prefix: str, retention_days: int):
    """
    Delete old backups from GCS based on retention policy
    
    Args:
        bucket: GCS bucket name
        prefix: GCS object prefix
        retention_days: Number of days to retain backups
    """
    try:
        from google.cloud import storage
        
        storage_client = storage.Client()
        bucket_obj = storage_client.bucket(bucket)
        
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        logger.info(f"Cleaning up backups older than {cutoff_date.date()}")
        
        # List blobs
        blobs = bucket_obj.list_blobs(prefix=prefix)
        
        deleted_count = 0
        for blob in blobs:
            if blob.time_created.replace(tzinfo=None) < cutoff_date:
                logger.debug(f"Deleting old backup: {blob.name}")
                blob.delete()
                deleted_count += 1
        
        if deleted_count > 0:
            logger.info(f"Deleted {deleted_count} old backups")
        else:
            logger.info("No old backups to delete")
            
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")


def find_latest_backup(backup_dir: Path) -> Path:
    """Find the most recent backup file"""
    backup_files = list(backup_dir.glob("*.sql.gz"))
    
    if not backup_files:
        raise FileNotFoundError(f"No backup files found in {backup_dir}")
    
    latest_backup = max(backup_files, key=lambda p: p.stat().st_mtime)
    logger.info(f"Found latest backup: {latest_backup}")
    
    return latest_backup


def main():
    parser = argparse.ArgumentParser(description="Upload database backup to cloud storage")
    parser.add_argument('--backup-dir', type=str, default='./backups', help='Backup directory')
    parser.add_argument('--backup-file', type=str, help='Specific backup file to upload')
    parser.add_argument('--provider', type=str, choices=['s3', 'gcs'], required=True, help='Cloud provider')
    parser.add_argument('--bucket', type=str, required=True, help='Bucket name')
    parser.add_argument('--prefix', type=str, default='backups', help='Object prefix/path')
    parser.add_argument('--retention-days', type=int, default=90, help='Retention period in days')
    parser.add_argument('--no-cleanup', action='store_true', help='Skip cleanup of old backups')
    parser.add_argument('--verbose', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    setup_logging(args.verbose)
    
    try:
        # Find backup file
        if args.backup_file:
            backup_file = Path(args.backup_file)
        else:
            backup_dir = Path(args.backup_dir)
            backup_file = find_latest_backup(backup_dir)
        
        if not backup_file.exists():
            logger.error(f"Backup file not found: {backup_file}")
            sys.exit(1)
        
        logger.info(f"Uploading backup: {backup_file}")
        logger.info(f"Size: {backup_file.stat().st_size / 1024 / 1024:.2f} MB")
        logger.info(f"Provider: {args.provider.upper()}")
        logger.info(f"Bucket: {args.bucket}")
        
        # Upload to cloud storage
        if args.provider == 's3':
            uri = upload_to_s3(backup_file, args.bucket, args.prefix)
        elif args.provider == 'gcs':
            uri = upload_to_gcs(backup_file, args.bucket, args.prefix)
        else:
            logger.error(f"Unknown provider: {args.provider}")
            sys.exit(1)
        
        logger.success(f"✓ Backup uploaded successfully: {uri}")
        
        # Cleanup old backups
        if not args.no_cleanup:
            logger.info(f"Cleaning up backups older than {args.retention_days} days...")
            if args.provider == 's3':
                cleanup_old_backups_s3(args.bucket, args.prefix, args.retention_days)
            elif args.provider == 'gcs':
                cleanup_old_backups_gcs(args.bucket, args.prefix, args.retention_days)
        
        sys.exit(0)
        
    except Exception as e:
        logger.error(f"Backup upload failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
