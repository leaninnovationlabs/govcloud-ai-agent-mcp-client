output "data_lake_bucket_name" {
  description = "Name of the S3 data lake bucket"
  value       = aws_s3_bucket.data_lake.bucket
}

output "data_lake_bucket_arn" {
  description = "ARN of the S3 data lake bucket"
  value       = aws_s3_bucket.data_lake.arn
}

output "athena_results_bucket_name" {
  description = "Name of the Athena results bucket"
  value       = aws_s3_bucket.athena_results.bucket
}

output "glue_database_name" {
  description = "Name of the Glue catalog database"
  value       = aws_glue_catalog_database.maritime_db.name
}

output "glue_crawler_name" {
  description = "Name of the Glue crawler"
  value       = aws_glue_crawler.maritime_crawler.name
}

output "athena_workgroup_name" {
  description = "Name of the Athena workgroup"
  value       = aws_athena_workgroup.maritime_analytics.name
}

output "environment" {
  description = "Environment name"
  value       = local.environment
}

output "aws_region" {
  description = "AWS region"
  value       = local.config.region
}

output "sample_athena_queries" {
  description = "Sample Athena queries to test the data lake"
  value = [
    "-- Query ship parts inventory",
    "SELECT * FROM ${aws_glue_catalog_database.maritime_db.name}.ship_parts LIMIT 10;",
    "",
    "-- Query food inventory",
    "SELECT * FROM ${aws_glue_catalog_database.maritime_db.name}.food_inventory WHERE food_type IN ('hot_dogs', 'chicken_tenders') LIMIT 10;",
    "",
    "-- Query vessels",
    "SELECT * FROM ${aws_glue_catalog_database.maritime_db.name}.vessels LIMIT 10;",
    "",
    "-- Query shipments",
    "SELECT * FROM ${aws_glue_catalog_database.maritime_db.name}.shipments LIMIT 10;",
    "",
    "-- Join query: Find vessels carrying food",
    "SELECT v.vessel_name, v.vessel_type, s.destination_port, f.food_type, f.quantity",
    "FROM ${aws_glue_catalog_database.maritime_db.name}.vessels v",
    "JOIN ${aws_glue_catalog_database.maritime_db.name}.shipments s ON v.vessel_id = s.vessel_id",
    "JOIN ${aws_glue_catalog_database.maritime_db.name}.food_inventory f ON s.shipment_id = f.shipment_id",
    "WHERE f.food_type IN ('hot_dogs', 'chicken_tenders')",
    "LIMIT 20;"
  ]
} 