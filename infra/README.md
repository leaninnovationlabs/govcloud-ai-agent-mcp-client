# Maritime Shipping Data Lake Infrastructure

This directory contains Terraform infrastructure code to deploy a complete AWS data lake solution for maritime shipping analytics. The infrastructure includes S3 storage, AWS Glue for data cataloging, and Amazon Athena for querying.

## Architecture

The data lake consists of:

- **S3 Data Lake Bucket**: Stores parquet files organized by table/dataset
- **S3 Athena Results Bucket**: Stores query results from Athena
- **AWS Glue Database**: Data catalog containing table schemas
- **AWS Glue Crawler**: Automatically discovers and catalogs data schemas
- **Amazon Athena Workgroup**: Query engine for SQL analytics
- **IAM Roles & Policies**: Secure access between services

## Sample Data

The solution includes generators for realistic maritime shipping data:

- **Ship Parts**: Inventory of maritime components (engines, navigation equipment, etc.)
- **Food Inventory**: Galley supplies including hot dogs and chicken tenders 🌭🍗
- **Vessels**: Fleet information (container ships, tankers, cargo vessels)
- **Shipments**: Logistics and shipping manifest data

## Quick Start

### Prerequisites

- AWS CLI configured with appropriate credentials
- Terraform installed (>= 1.0)
- Python 3.8+ with pip

### 1. Deploy Infrastructure

```bash
# Deploy development environment
make infra-up

# Or deploy production environment
make infra-up INFRA_ENV=prod
```

This will:
- Initialize Terraform
- Plan and apply the infrastructure
- Create all AWS resources

### 2. Generate and Upload Sample Data

```bash
# Generate parquet files and upload to S3
make infra-data
```

This will:
- Install Python dependencies
- Generate realistic sample data
- Upload parquet files to S3
- Run Glue crawler to discover schemas
- Create queryable tables in the data catalog

### 3. Query Your Data Lake

1. Open the [AWS Athena Console](https://console.aws.amazon.com/athena/)
2. Select the workgroup: `maritime-analytics-dev` (or `-prod`)
3. Choose database: `maritime_shipping_db`
4. Run SQL queries against your tables

## Sample Queries

```sql
-- Find all hot dogs and chicken tenders in inventory
SELECT food_type, quantity, unit, supplier, storage_type
FROM maritime_shipping_db.food_inventory 
WHERE food_type IN ('hot_dogs', 'chicken_tenders');

-- Get vessel information with current status
SELECT vessel_name, vessel_type, gross_tonnage, current_port, status
FROM maritime_shipping_db.vessels 
ORDER BY gross_tonnage DESC;

-- Join vessels with their shipments
SELECT v.vessel_name, v.vessel_type, s.origin_port, s.destination_port, s.cargo_type
FROM maritime_shipping_db.vessels v
JOIN maritime_shipping_db.shipments s ON v.vessel_id = s.vessel_id
WHERE s.status = 'In Transit';

-- Analyze food logistics by vessel
SELECT v.vessel_name, s.destination_port, f.food_type, f.quantity
FROM maritime_shipping_db.vessels v
JOIN maritime_shipping_db.shipments s ON v.vessel_id = s.vessel_id  
JOIN maritime_shipping_db.food_inventory f ON s.shipment_id = f.shipment_id
WHERE f.food_type IN ('hot_dogs', 'chicken_tenders')
ORDER BY v.vessel_name, f.food_type;
```

## Makefile Commands

| Command | Description |
|---------|-------------|
| `make infra-up` | Deploy the complete data lake infrastructure |
| `make infra-down` | Destroy all infrastructure (⚠️ permanent!) |
| `make infra-data` | Generate sample data and upload to S3 |
| `make infra-status` | Show current infrastructure status |
| `make infra-plan` | Preview infrastructure changes |
| `make infra-init` | Initialize Terraform only |

## Environment Configuration

The infrastructure supports multiple environments through YAML configuration files:

- `config/dev.yml` - Development environment
- `config/prod.yml` - Production environment

Switch environments using the `INFRA_ENV` variable:

```bash
# Deploy to production
make infra-up INFRA_ENV=prod

# Generate data for production
make infra-data INFRA_ENV=prod
```

## Configuration Structure

```yaml
project_name: "maritime-shipping-lake"
environment: "dev"
region: "us-east-1"

s3:
  bucket_name: "maritime-shipping-data-lake-dev"
  enable_versioning: true
  force_destroy: true

glue:
  database_name: "maritime_shipping_db"
  crawler_name: "maritime-data-crawler"
  
athena:
  workgroup_name: "maritime-analytics"
  results_bucket: "maritime-athena-results-dev"

tags:
  Environment: "dev"
  Project: "maritime-shipping-analytics"
  Owner: "data-engineering"
  ManagedBy: "terraform"
```

## File Structure

```
infra/
├── config/
│   ├── dev.yml                    # Dev environment config
│   └── prod.yml                   # Prod environment config
├── scripts/
│   ├── generate_sample_data.py    # Data generator
│   └── upload_data_and_crawl.py   # S3 uploader & crawler
├── data/                          # Generated parquet files (created)
├── main.tf                        # Main Terraform configuration
├── variables.tf                   # Input variables
├── outputs.tf                     # Output values
├── requirements.txt               # Python dependencies
└── README.md                      # This file
```

## Security Features

- S3 buckets are private with public access blocked
- Server-side encryption enabled (AES256)
- IAM roles follow principle of least privilege
- Versioning enabled for data protection
- Athena results are encrypted

## Cost Optimization

- S3 Intelligent Tiering for automatic cost optimization
- Serverless services (Athena, Glue) - pay per use
- Development environment allows force destroy for cleanup
- Production environment protects against accidental deletion

## Troubleshooting

### Common Issues

1. **AWS Credentials**: Ensure your AWS CLI is configured with valid credentials
2. **Terraform State**: If deployment fails, check for existing Terraform state files
3. **Permissions**: Verify your AWS user has permissions for S3, Glue, Athena, and IAM
4. **Python Dependencies**: Run `pip install -r requirements.txt` if scripts fail

### Cleanup

To completely remove all infrastructure:

```bash
make infra-down
```

⚠️ **Warning**: This permanently deletes all data and infrastructure!

## Next Steps

After setting up your data lake:

1. Explore the sample data in Athena
2. Create custom dashboards with Amazon QuickSight
3. Set up automated ETL jobs with AWS Glue
4. Implement data governance with AWS Lake Formation
5. Add real-time streaming with Amazon Kinesis

## Support

For issues or questions:
1. Check the AWS Glue and Athena documentation
2. Review CloudWatch logs for detailed error messages
3. Use `make infra-status` to check current infrastructure state 