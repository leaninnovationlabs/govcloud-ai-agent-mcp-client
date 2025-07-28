terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.4"
    }
  }
}

provider "aws" {
  region = local.config.region
}

# Load configuration from YAML
locals {
  environment = var.environment
  config      = yamldecode(file("${path.module}/config/${local.environment}.yml"))
}

# Random suffix for unique resource names
resource "random_id" "suffix" {
  byte_length = 4
}

# Data lake S3 bucket
resource "aws_s3_bucket" "data_lake" {
  bucket        = "${local.config.s3.bucket_name}-${random_id.suffix.hex}"
  force_destroy = local.config.s3.force_destroy

  tags = local.config.tags
}

# S3 bucket versioning
resource "aws_s3_bucket_versioning" "data_lake" {
  bucket = aws_s3_bucket.data_lake.id
  versioning_configuration {
    status = local.config.s3.enable_versioning ? "Enabled" : "Disabled"
  }
}

# S3 bucket encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "data_lake" {
  bucket = aws_s3_bucket.data_lake.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# S3 bucket public access block
resource "aws_s3_bucket_public_access_block" "data_lake" {
  bucket = aws_s3_bucket.data_lake.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Athena results S3 bucket
resource "aws_s3_bucket" "athena_results" {
  bucket        = "${local.config.athena.results_bucket}-${random_id.suffix.hex}"
  force_destroy = local.config.s3.force_destroy

  tags = local.config.tags
}

# Athena results bucket encryption
resource "aws_s3_bucket_server_side_encryption_configuration" "athena_results" {
  bucket = aws_s3_bucket.athena_results.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Athena results bucket public access block
resource "aws_s3_bucket_public_access_block" "athena_results" {
  bucket = aws_s3_bucket.athena_results.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Glue catalog database
resource "aws_glue_catalog_database" "maritime_db" {
  name        = local.config.glue.database_name
  description = "Maritime shipping data warehouse"

  tags = local.config.tags
}

# IAM role for Glue crawler
resource "aws_iam_role" "glue_crawler_role" {
  name = "${local.config.project_name}-glue-crawler-role-${local.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "glue.amazonaws.com"
        }
      }
    ]
  })

  tags = local.config.tags
}

# IAM policy for Glue crawler S3 access
resource "aws_iam_policy" "glue_s3_policy" {
  name        = "${local.config.project_name}-glue-s3-policy-${local.environment}"
  description = "IAM policy for Glue crawler to access S3"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:GetObjectVersion",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.data_lake.arn,
          "${aws_s3_bucket.data_lake.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject"
        ]
        Resource = [
          "${aws_s3_bucket.athena_results.arn}/*"
        ]
      }
    ]
  })
}

# Attach AWS managed policy for Glue service role
resource "aws_iam_role_policy_attachment" "glue_service_role" {
  role       = aws_iam_role.glue_crawler_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}

# Attach custom S3 policy to Glue role
resource "aws_iam_role_policy_attachment" "glue_s3_policy" {
  role       = aws_iam_role.glue_crawler_role.name
  policy_arn = aws_iam_policy.glue_s3_policy.arn
}

# Glue crawler for data discovery
resource "aws_glue_crawler" "maritime_crawler" {
  database_name = aws_glue_catalog_database.maritime_db.name
  name          = "${local.config.glue.crawler_name}-${local.environment}"
  role          = aws_iam_role.glue_crawler_role.arn

  s3_target {
    path = "s3://${aws_s3_bucket.data_lake.bucket}/"
  }

  configuration = jsonencode({
    Version = 1.0
    CrawlerOutput = {
      Partitions = { AddOrUpdateBehavior = "InheritFromTable" }
    }
  })

  tags = local.config.tags
}

# Athena workgroup
resource "aws_athena_workgroup" "maritime_analytics" {
  name = "${local.config.athena.workgroup_name}-${local.environment}"

  configuration {
    enforce_workgroup_configuration    = true
    publish_cloudwatch_metrics_enabled = true

    result_configuration {
      output_location = "s3://${aws_s3_bucket.athena_results.bucket}/"

      encryption_configuration {
        encryption_option = "SSE_S3"
      }
    }
  }

  tags = local.config.tags
} 