#!/usr/bin/env python3
"""
Upload generated parquet data to S3 and trigger Glue crawler.
This script should be run after Terraform deployment.
"""

import os
import sys
import boto3
import json
import time
import argparse
from pathlib import Path

def get_terraform_outputs(terraform_dir):
    """Get outputs from Terraform state"""
    try:
        import subprocess
        result = subprocess.run(
            ['terraform', 'output', '-json'],
            cwd=terraform_dir,
            capture_output=True,
            text=True,
            check=True
        )
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"❌ Error getting Terraform outputs: {e}")
        print(f"   Make sure you've run 'terraform apply' first")
        sys.exit(1)
    except FileNotFoundError:
        print("❌ Terraform not found in PATH")
        sys.exit(1)

def upload_file_to_s3(s3_client, local_file, bucket_name, s3_key):
    """Upload a file to S3"""
    try:
        print(f"📤 Uploading {local_file} to s3://{bucket_name}/{s3_key}")
        s3_client.upload_file(local_file, bucket_name, s3_key)
        print(f"✅ Successfully uploaded {s3_key}")
        return True
    except Exception as e:
        print(f"❌ Error uploading {local_file}: {e}")
        return False

def upload_parquet_files(s3_client, data_dir, bucket_name):
    """Upload all parquet files to S3"""
    data_path = Path(data_dir)
    if not data_path.exists():
        print(f"❌ Data directory {data_dir} not found")
        print("   Run the data generation script first:")
        print("   cd infra/scripts && python generate_sample_data.py")
        return False
    
    parquet_files = list(data_path.glob("*.parquet"))
    if not parquet_files:
        print(f"❌ No parquet files found in {data_dir}")
        return False
    
    print(f"📦 Found {len(parquet_files)} parquet files to upload")
    
    success_count = 0
    for parquet_file in parquet_files:
        # Use the filename (without extension) as the S3 "table" prefix
        table_name = parquet_file.stem
        s3_key = f"{table_name}/{parquet_file.name}"
        
        if upload_file_to_s3(s3_client, str(parquet_file), bucket_name, s3_key):
            success_count += 1
    
    print(f"\n📊 Upload Summary: {success_count}/{len(parquet_files)} files uploaded successfully")
    return success_count == len(parquet_files)

def trigger_glue_crawler(glue_client, crawler_name):
    """Trigger the Glue crawler and wait for completion"""
    try:
        print(f"🔍 Starting Glue crawler: {crawler_name}")
        
        # Check if crawler is already running
        response = glue_client.get_crawler(Name=crawler_name)
        state = response['Crawler']['State']
        
        if state == 'RUNNING':
            print("⏳ Crawler is already running, waiting for completion...")
        else:
            # Start the crawler
            glue_client.start_crawler(Name=crawler_name)
            print("✅ Crawler started successfully")
        
        # Wait for crawler to complete
        print("⏳ Waiting for crawler to complete...")
        max_wait_time = 300  # 5 minutes
        wait_time = 0
        
        while wait_time < max_wait_time:
            time.sleep(10)
            wait_time += 10
            
            response = glue_client.get_crawler(Name=crawler_name)
            state = response['Crawler']['State']
            
            print(f"   Crawler state: {state} (waited {wait_time}s)")
            
            if state == 'READY':
                print("✅ Crawler completed successfully!")
                
                # Get last crawl info
                last_crawl = response['Crawler']['LastCrawl']
                if last_crawl:
                    status = last_crawl.get('Status', 'Unknown')
                    message = last_crawl.get('ErrorMessage', '')
                    tables_created = last_crawl.get('TablesCreated', 0)
                    tables_updated = last_crawl.get('TablesUpdated', 0)
                    
                    print(f"   Last crawl status: {status}")
                    print(f"   Tables created: {tables_created}")
                    print(f"   Tables updated: {tables_updated}")
                    
                    if message:
                        print(f"   Message: {message}")
                
                return True
            elif state == 'STOPPING':
                print("⚠️  Crawler is stopping")
                continue
            elif state in ['FAILED', 'CANCELLED']:
                print(f"❌ Crawler {state.lower()}")
                if 'LastCrawl' in response['Crawler'] and response['Crawler']['LastCrawl']:
                    error_msg = response['Crawler']['LastCrawl'].get('ErrorMessage', 'No error message')
                    print(f"   Error: {error_msg}")
                return False
        
        print(f"⏰ Crawler did not complete within {max_wait_time} seconds")
        return False
        
    except Exception as e:
        print(f"❌ Error with Glue crawler: {e}")
        return False

def list_discovered_tables(glue_client, database_name):
    """List tables discovered by the crawler"""
    try:
        print(f"\n📋 Tables discovered in database '{database_name}':")
        
        response = glue_client.get_tables(DatabaseName=database_name)
        tables = response.get('TableList', [])
        
        if not tables:
            print("   No tables found")
            return
        
        for table in tables:
            table_name = table['Name']
            storage_descriptor = table.get('StorageDescriptor', {})
            location = storage_descriptor.get('Location', 'Unknown')
            input_format = storage_descriptor.get('InputFormat', 'Unknown')
            columns = storage_descriptor.get('Columns', [])
            
            print(f"\n  📊 Table: {table_name}")
            print(f"     Location: {location}")
            print(f"     Format: {input_format}")
            print(f"     Columns: {len(columns)}")
            
            if columns:
                print("     Schema:")
                for col in columns[:5]:  # Show first 5 columns
                    col_name = col.get('Name', 'unknown')
                    col_type = col.get('Type', 'unknown')
                    print(f"       - {col_name}: {col_type}")
                if len(columns) > 5:
                    print(f"       ... and {len(columns) - 5} more columns")
        
    except Exception as e:
        print(f"❌ Error listing tables: {e}")

def main():
    parser = argparse.ArgumentParser(description='Upload data to S3 and run Glue crawler')
    parser.add_argument('--terraform-dir', default='..', help='Terraform directory path')
    parser.add_argument('--data-dir', default='../data', help='Data directory containing parquet files')
    parser.add_argument('--skip-upload', action='store_true', help='Skip file upload, only run crawler')
    parser.add_argument('--skip-crawler', action='store_true', help='Skip crawler, only upload files')
    
    args = parser.parse_args()
    
    print("🚢 Maritime Data Lake - Upload and Crawl")
    print("=" * 50)
    
    # Get Terraform outputs
    print("📋 Getting Terraform outputs...")
    terraform_outputs = get_terraform_outputs(args.terraform_dir)
    
    # Extract values from Terraform outputs
    bucket_name = terraform_outputs['data_lake_bucket_name']['value']
    crawler_name = terraform_outputs['glue_crawler_name']['value']
    database_name = terraform_outputs['glue_database_name']['value']
    region = terraform_outputs['aws_region']['value']
    
    print(f"   S3 Bucket: {bucket_name}")
    print(f"   Glue Crawler: {crawler_name}")
    print(f"   Glue Database: {database_name}")
    print(f"   AWS Region: {region}")
    
    # Initialize AWS clients
    try:
        s3_client = boto3.client('s3', region_name=region)
        glue_client = boto3.client('glue', region_name=region)
    except Exception as e:
        print(f"❌ Error initializing AWS clients: {e}")
        print("   Make sure your AWS credentials are configured")
        sys.exit(1)
    
    # Upload parquet files to S3
    if not args.skip_upload:
        print(f"\n📤 Uploading parquet files to S3...")
        if not upload_parquet_files(s3_client, args.data_dir, bucket_name):
            print("❌ Failed to upload all files")
            if not args.skip_crawler:
                print("   Skipping crawler due to upload failures")
                sys.exit(1)
    else:
        print("\n⏭️  Skipping file upload")
    
    # Run Glue crawler
    if not args.skip_crawler:
        print(f"\n🔍 Running Glue crawler...")
        if trigger_glue_crawler(glue_client, crawler_name):
            # List discovered tables
            list_discovered_tables(glue_client, database_name)
            
            print(f"\n🎉 Data lake setup complete!")
            print(f"\n🔗 Next steps:")
            print(f"   1. Open AWS Athena console")
            print(f"   2. Select workgroup: {terraform_outputs['athena_workgroup_name']['value']}")
            print(f"   3. Run queries against database: {database_name}")
            print(f"\n📝 Sample queries are available in Terraform outputs")
        else:
            print("❌ Crawler failed")
            sys.exit(1)
    else:
        print("\n⏭️  Skipping crawler")
    
    print("\n✅ All operations completed successfully!")

if __name__ == "__main__":
    main() 