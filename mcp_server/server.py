import logging
import os
from typing import Optional
from pydantic import BaseModel, Field, field_validator

from fastmcp import FastMCP, Context
from starlette.requests import Request
from starlette.responses import JSONResponse

from .models import TableSchema, QueryResult, SchemaDiscoveryResult, AthenaError, SQLQuery
from .athena_service import AthenaService

logger = logging.getLogger(__name__)


class DiscoverSchemaArgs(BaseModel):
    include_metadata: bool = Field(
        False, 
        description="Include detailed metadata like creation time and parameters"
    )


class GetTableSchemaArgs(BaseModel):
    database_name: str = Field(
        ..., 
        min_length=1, 
        description="Database name (e.g., 'analytics', 'raw_data')"
    )
    table_name: str = Field(
        ..., 
        min_length=1, 
        description="Table name to inspect for column definitions and partitions"
    )
    
    @field_validator('database_name', 'table_name')
    @classmethod
    def validate_names(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Name cannot be empty or whitespace")
        return v.strip()


class ExecuteQueryArgs(BaseModel):
    sql: str = Field(
        ..., 
        min_length=1, 
        description="AWS Athena SQL query (SELECT/SHOW/DESCRIBE only). Use partition columns in WHERE clauses to reduce costs."
    )
    database_name: Optional[str] = Field(
        None, 
        description="Target database. Uses default from env if not specified."
    )
    limit: int = Field(
        100, 
        description="Max rows to return (safety limit)", 
        ge=1, 
        le=10000
    )
    
    @field_validator('sql')
    @classmethod
    def validate_sql(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("SQL query cannot be empty")
        return v.strip()


class GenerateQueryArgs(BaseModel):
    prompt: str = Field(
        ..., 
        min_length=1, 
        description="Natural language description. Be specific about filters, aggregations, and desired output."
    )
    database_name: Optional[str] = Field(
        None, 
        description="Database context for schema awareness"
    )
    include_explanation: bool = Field(
        True, 
        description="Include query explanation and optimization hints"
    )


class AthenaMCPServer:
    def __init__(self):
        self.mcp = FastMCP(
            name="athena-mcp-server",
            instructions="""AWS Athena data lake query server with AI-powered SQL generation.

Key capabilities:
- Schema discovery across S3-based data lakes
- Natural language to optimized SQL conversion using Claude 3.5
- Cost-aware query execution with partition optimization
- Automatic query safety validation

Best practices:
- Always filter on partition columns when available
- Use LIMIT clauses to control scan costs
- Prefer columnar formats (Parquet/ORC) for better performance
- Check table schemas before querying to understand data types"""
        )
        
        region = os.getenv("AWS_REGION", "us-east-1")
        s3_bucket = os.getenv("ATHENA_S3_BUCKET")
        s3_prefix = os.getenv("ATHENA_S3_PREFIX", "athena-results/")
        database = os.getenv("ATHENA_DATABASE")
        workgroup = os.getenv("ATHENA_WORKGROUP", "primary")
        bedrock_model = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0")
        bedrock_region = os.getenv("BEDROCK_REGION", region)
        
        if not s3_bucket:
            raise ValueError("ATHENA_S3_BUCKET environment variable is required")
        
        self.athena_service = AthenaService(
            region=region,
            s3_bucket=s3_bucket,
            s3_prefix=s3_prefix,
            database=database,
            workgroup=workgroup,
            bedrock_model_id=bedrock_model,
            bedrock_region=bedrock_region
        )
        
        self._register_custom_routes()
        self._register_tools()
        self._register_prompts()
    
    def _register_custom_routes(self):
        @self.mcp.custom_route("/health", methods=["GET"])
        async def health_check(request: Request) -> JSONResponse:
            return JSONResponse(content={
                "status": "healthy", 
                "service": "athena-mcp-server",
                "aws_region": os.getenv("AWS_REGION", "us-east-1"),
                "bedrock_model": os.getenv("BEDROCK_MODEL_ID", "claude-3-5-sonnet")
            })
        
        @self.mcp.custom_route("/", methods=["GET"])
        async def root(request: Request) -> JSONResponse:
            tool_names = [tool.name for tool in self.mcp.tools.values()]
            return JSONResponse(content={
                "service": "Athena MCP Server",
                "version": "2.0.0",
                "transport": "streamable-http",
                "endpoints": {
                    "mcp": "/mcp",
                    "health": "/health"
                },
                "description": "AWS Athena query server with AI-powered SQL generation via Claude 3.5",
                "mcp_capabilities": {
                    "tools": tool_names,
                    "prompts": True,
                    "resources": False
                },
                "features": [
                    "Natural language to SQL conversion",
                    "Cost-optimized query execution",
                    "Schema discovery and exploration",
                    "Partition-aware query generation"
                ]
            })
    
    def _register_tools(self):
        @self.mcp.tool(
            description="""Discover all databases and tables in your AWS data lake.
            
Returns hierarchical view of databases with table counts and names.
Use this first to understand available data before querying.

Cost consideration: This operation scans metadata only (no data charges)."""
        )
        async def discover_schema(ctx: Context, args: DiscoverSchemaArgs) -> SchemaDiscoveryResult:
            await ctx.info("📊 Discovering data lake schema...")
            try:
                result = await self.athena_service.discover_schema()
                
                if result.databases:
                    await ctx.info(f"Found {len(result.databases)} databases with {result.total_tables} total tables")
                else:
                    await ctx.warning("No databases found in data catalog")
                    
                return result
            except AthenaError as e:
                await ctx.error(f"Schema discovery failed: {e.message}")
                raise
        
        @self.mcp.tool(
            description="""Get detailed schema for a specific table.
            
Returns:
- Column names, types, and comments
- Partition keys (critical for query optimization)
- Storage location and format
- Table metadata

Use partition columns in WHERE clauses to dramatically reduce query costs."""
        )
        async def get_table_schema(ctx: Context, args: GetTableSchemaArgs) -> TableSchema:
            await ctx.info(f"🔍 Inspecting table {args.database_name}.{args.table_name}")
            try:
                schema = await self.athena_service.get_table_schema(
                    args.database_name, 
                    args.table_name
                )
                
                if schema.partition_keys:
                    partition_names = [pk['name'] for pk in schema.partition_keys]
                    await ctx.info(f"Table has {len(schema.partition_keys)} partition(s): {', '.join(partition_names)}")
                    await ctx.info("💡 Filter on these columns to reduce query costs")
                
                return schema
            except AthenaError as e:
                await ctx.error(f"Failed to get table schema: {e.message}")
                raise
        
        @self.mcp.tool(
            description="""Execute SQL queries against S3-based data lake via AWS Athena.
            
Supports: SELECT, SHOW TABLES, DESCRIBE
Security: Only read operations allowed
Cost optimization tips:
- Filter on partition columns (date, region, etc)
- Use LIMIT to control data scanned
- Specify only needed columns
- Prefer Parquet/ORC tables over CSV

Query results include execution time and data scanned for cost monitoring."""
        )
        async def execute_query(ctx: Context, args: ExecuteQueryArgs) -> QueryResult:
            await ctx.info(f"🚀 Executing query on database: {args.database_name or 'default'}")
            try:
                sql = args.sql
                if args.limit and 'LIMIT' not in sql.upper():
                    sql = f"{sql} LIMIT {args.limit}"
                    await ctx.info(f"Added safety limit: {args.limit} rows")
                
                result = await self.athena_service.execute_query(sql, args.database_name)
                
                if result.status == 'SUCCEEDED':
                    if result.data_scanned_bytes:
                        gb_scanned = result.data_scanned_bytes / (1024**3)
                        await ctx.info(f"✅ Query completed in {result.execution_time_ms}ms, scanned {gb_scanned:.3f}GB")
                    if result.rows:
                        await ctx.info(f"Returned {len(result.rows)} rows")
                else:
                    await ctx.error(f"Query failed: {result.error_message}")
                
                return result
            except AthenaError as e:
                await ctx.error(f"Query execution failed: {e.message}")
                raise
        
        @self.mcp.tool(
            description="""Generate optimized Athena SQL from natural language using Claude 3.5.
            
Examples:
- "Show me daily sales totals for last month"
- "Find top 10 customers by revenue with their regions"
- "Count unique users per product category"

The AI understands:
- Table relationships and schemas
- Partition optimization strategies
- Athena-specific SQL syntax
- Cost-efficient query patterns

Returns generated SQL with explanation and optimization hints."""
        )
        async def generate_query(ctx: Context, args: GenerateQueryArgs) -> str:
            await ctx.info(f"🤖 Generating SQL with Claude 3.5: {args.prompt[:50]}...")
            try:
                sql = await self.athena_service.generate_query_from_prompt(
                    args.prompt, 
                    args.database_name
                )
                logger.info(f"Generated SQL: {sql}")
                await ctx.info("✅ SQL generated successfully")
                return sql
            except AthenaError as e:
                await ctx.error(f"Query generation failed: {e.message}")
                raise

        @self.mcp.tool(
            description="""Generate and immediately execute a query from natural language.
            
Combines AI-powered SQL generation with execution in one step.
Perfect for exploratory data analysis and ad-hoc queries.

Safety features:
- Automatic LIMIT clause addition
- Query validation before execution
- Cost estimation when possible"""
        )
        async def query_from_prompt(ctx: Context, args: GenerateQueryArgs) -> QueryResult:
            await ctx.info(f"🤖 Generating and executing query: {args.prompt[:50]}...")
            try:
                sql = await self.athena_service.generate_query_from_prompt(
                    args.prompt, 
                    args.database_name
                )
                logger.info(f"Generated SQL: {sql}")
                await ctx.info(f"Generated SQL: {sql}...")
                
                result = await self.athena_service.execute_query(sql, args.database_name)
                
                if result.status == 'SUCCEEDED' and result.data_scanned_bytes:
                    gb_scanned = result.data_scanned_bytes / (1024**3)
                    cost_estimate = gb_scanned * 5.0
                    await ctx.info(f"💰 Estimated query cost: ${cost_estimate:.4f} ({gb_scanned:.3f}GB @ $5/TB)")
                
                return result
            except AthenaError as e:
                await ctx.error(f"Query generation and execution failed: {e.message}")
                raise
    
    def _register_prompts(self):
        @self.mcp.prompt
        async def athena_best_practices(ctx: Context) -> str:
            return """# AWS Athena Query Optimization Guide

## 🎯 Query Performance Best Practices

### 1. Partition Filtering (Most Important!)
Always filter on partition columns to reduce data scanned:
```sql
SELECT * FROM events 
WHERE year = 2024 AND month = 12 AND day = 15
```

### 2. Column Selection
Specify only needed columns instead of SELECT *:
```sql
-- ❌ Bad: Scans all columns
SELECT * FROM large_table

-- ✅ Good: Scans only needed columns  
SELECT user_id, event_type, timestamp FROM large_table
```

### 3. File Formats
- **Parquet/ORC**: Columnar formats, 10x faster than CSV
- **Compression**: Use Snappy or ZSTD
- **File Size**: Aim for 100-200MB files

### 4. Aggregation Optimization
Use approximate functions for large datasets:
```sql
-- Exact count (expensive)
SELECT COUNT(DISTINCT user_id) FROM events

-- Approximate count (90% cheaper)
SELECT APPROX_DISTINCT(user_id) FROM events
```

## 💰 Cost Optimization

### Pricing Model
- $5 per TB of data scanned
- Charged per query, rounded up to nearest 10MB
- No charges for DDL, failed queries, or metadata

### Cost Reduction Strategies
1. **Partition Design**: Date-based partitions are most common
2. **Projection Pushdown**: Let Athena skip unnecessary columns
3. **Predicate Pushdown**: Filter early in the query
4. **Data Compression**: 3:1 compression = 66% cost savings

## 🔍 Schema Discovery Workflow

1. List all databases:
```sql
SHOW DATABASES
```

2. Explore tables in a database:
```sql
SHOW TABLES IN analytics
```

3. Inspect table schema:
```sql
DESCRIBE analytics.user_events
```

4. Check partitions:
```sql
SHOW PARTITIONS analytics.user_events
```

## 🚀 Advanced Patterns

### Window Functions
```sql
SELECT user_id, 
       event_time,
       LAG(event_time) OVER (PARTITION BY user_id ORDER BY event_time) as prev_event
FROM events
```

### CTEs for Complex Queries
```sql
WITH daily_stats AS (
    SELECT DATE(event_time) as event_date,
           COUNT(*) as event_count
    FROM events
    WHERE year = 2024
    GROUP BY DATE(event_time)
)
SELECT * FROM daily_stats WHERE event_count > 1000
```

## 🛡️ Query Safety

- Always include LIMIT for exploration
- Use EXPLAIN to understand query plan
- Monitor QueryExecutionTime and DataScannedInBytes
- Set up workgroup query limits

Remember: The key to cost-effective Athena queries is minimizing data scanned through smart partitioning and column selection!"""
        
        @self.mcp.prompt
        async def natural_language_examples(ctx: Context) -> str:
            return """# Natural Language Query Examples for Athena

## 📊 Basic Aggregations

**Prompt**: "Show me the total number of orders per day last week"
**Generated SQL**:
```sql
SELECT DATE(order_timestamp) as order_date,
       COUNT(*) as total_orders,
       SUM(order_amount) as total_revenue
FROM orders
WHERE order_timestamp >= CURRENT_DATE - INTERVAL '7' DAY
GROUP BY DATE(order_timestamp)
ORDER BY order_date DESC
```

## 🔝 Top-N Queries

**Prompt**: "Find the top 10 products by revenue this month"
**Generated SQL**:
```sql
SELECT product_id,
       product_name,
       SUM(quantity * unit_price) as total_revenue,
       COUNT(DISTINCT order_id) as order_count
FROM order_items
WHERE year = YEAR(CURRENT_DATE) 
  AND month = MONTH(CURRENT_DATE)
GROUP BY product_id, product_name
ORDER BY total_revenue DESC
LIMIT 10
```

## 📈 Time Series Analysis

**Prompt**: "Show me hourly user activity trends for the past 24 hours"
**Generated SQL**:
```sql
SELECT DATE_TRUNC('hour', event_timestamp) as hour,
       COUNT(DISTINCT user_id) as unique_users,
       COUNT(*) as total_events
FROM user_events  
WHERE event_timestamp >= CURRENT_TIMESTAMP - INTERVAL '24' HOUR
GROUP BY DATE_TRUNC('hour', event_timestamp)
ORDER BY hour
```

## 🔗 Join Operations

**Prompt**: "Get customer details with their order summary"
**Generated SQL**:
```sql
WITH customer_orders AS (
    SELECT customer_id,
           COUNT(*) as order_count,
           SUM(total_amount) as lifetime_value,
           MAX(order_date) as last_order_date
    FROM orders
    GROUP BY customer_id
)
SELECT c.customer_id,
       c.customer_name,
       c.email,
       co.order_count,
       co.lifetime_value,
       co.last_order_date
FROM customers c
JOIN customer_orders co ON c.customer_id = co.customer_id
WHERE co.lifetime_value > 1000
ORDER BY co.lifetime_value DESC
```

## 🎯 Funnel Analysis

**Prompt**: "Calculate conversion funnel from page view to purchase"
**Generated SQL**:
```sql
WITH funnel_stages AS (
    SELECT user_id,
           MAX(CASE WHEN event_type = 'page_view' THEN 1 ELSE 0 END) as viewed,
           MAX(CASE WHEN event_type = 'add_to_cart' THEN 1 ELSE 0 END) as added_to_cart,
           MAX(CASE WHEN event_type = 'checkout' THEN 1 ELSE 0 END) as checked_out,
           MAX(CASE WHEN event_type = 'purchase' THEN 1 ELSE 0 END) as purchased
    FROM events
    WHERE date >= CURRENT_DATE - INTERVAL '30' DAY
    GROUP BY user_id
)
SELECT 
    COUNT(*) as total_users,
    SUM(viewed) as viewed_count,
    SUM(added_to_cart) as cart_count,
    SUM(checked_out) as checkout_count,
    SUM(purchased) as purchase_count,
    ROUND(100.0 * SUM(added_to_cart) / NULLIF(SUM(viewed), 0), 2) as view_to_cart_rate,
    ROUND(100.0 * SUM(purchased) / NULLIF(SUM(viewed), 0), 2) as overall_conversion_rate
FROM funnel_stages
```

## 💡 Tips for Better Prompts

1. **Be Specific**: "revenue by product category" → "daily revenue by product category for December 2024"
2. **Mention Filters**: Include time ranges, specific values, or conditions
3. **Describe Output**: "ranked list", "summary statistics", "time series"
4. **Include Context**: Mention if you need joins, aggregations, or window functions

The AI understands business terminology and will map it to your schema automatically!"""
        
        @self.mcp.prompt
        async def troubleshooting_guide(ctx: Context) -> str:
            return """# Athena Troubleshooting Guide

## 🚫 Common Errors and Solutions

### 1. HIVE_METASTORE_ERROR
**Cause**: Table or database doesn't exist
**Solution**: 
- Verify database/table names with `SHOW DATABASES` and `SHOW TABLES`
- Check for typos and case sensitivity
- Ensure you have permissions

### 2. PERMISSION_DENIED
**Cause**: Insufficient S3 or Glue permissions
**Solution**:
- Verify IAM role has s3:GetObject on data location
- Check Glue catalog permissions
- Ensure Athena workgroup access

### 3. SYNTAX_ERROR
**Cause**: Invalid SQL syntax
**Solution**:
- Use backticks for reserved words: `date`, `user`, `order`
- Check Presto SQL documentation for Athena
- Validate JOIN conditions and GROUP BY clauses

### 4. S3_PATH_NOT_FOUND
**Cause**: Table points to non-existent S3 location
**Solution**:
- Run `MSCK REPAIR TABLE` to sync partitions
- Verify S3 path exists and has data
- Check table DDL with `SHOW CREATE TABLE`

## ⚡ Performance Issues

### Slow Queries
1. **Missing Partition Filters**
   ```sql
   -- Slow: Scans entire table
   SELECT * FROM events WHERE user_id = '123'
   
   -- Fast: Uses partition
   SELECT * FROM events WHERE date = '2024-12-15' AND user_id = '123'
   ```

2. **Large Result Sets**
   - Add LIMIT clause
   - Use aggregations instead of raw data
   - Write results to S3 with CTAS

3. **Inefficient Joins**
   - Join on partitioned columns when possible
   - Put smaller table on right side of JOIN
   - Use broadcast joins for small dimension tables

### Out of Memory
- Reduce columns in SELECT
- Add more specific WHERE conditions  
- Use approximate aggregations
- Increase workgroup resource limits

## 🔧 Maintenance Tasks

### Update Table Partitions
```sql
-- Add new partitions after data loads
MSCK REPAIR TABLE database.table_name

-- Or add specific partition
ALTER TABLE events ADD PARTITION (year='2024', month='12', day='15')
LOCATION 's3://bucket/data/year=2024/month=12/day=15/'
```

### Optimize Table Storage
```sql
-- Convert CSV to Parquet
CREATE TABLE optimized_events
WITH (
    format = 'PARQUET',
    parquet_compression = 'SNAPPY',
    partitioned_by = ARRAY['year', 'month', 'day']
)
AS SELECT * FROM events
```

### Clean Up Old Data
```sql
-- Drop old partitions
ALTER TABLE events DROP PARTITION (year='2023', month='01')
```

## 📊 Monitoring and Debugging

### Query History
Check CloudWatch Logs for:
- Query execution times
- Data scanned per query
- Failed query reasons

### Cost Analysis
```sql
-- Analyze query costs by user
SELECT query_execution_id,
       query,
       data_scanned_in_bytes / 1024.0 / 1024.0 / 1024.0 as gb_scanned,
       (data_scanned_in_bytes / 1024.0 / 1024.0 / 1024.0 * 5.0) as estimated_cost_usd
FROM information_schema.query_history
WHERE query_state = 'SUCCEEDED'
ORDER BY data_scanned_in_bytes DESC
```

Remember: Most Athena issues stem from inefficient queries or incorrect permissions. Always check partitions first!"""
    
    async def cleanup(self):
        await self.athena_service.close()


def create_mcp_server() -> AthenaMCPServer:
    return AthenaMCPServer()