import logging
import os
from typing import Optional
from pydantic import BaseModel, Field

from fastmcp import FastMCP, Context
from starlette.requests import Request
from starlette.responses import JSONResponse

from .models import TableSchema, QueryResult, SchemaDiscoveryResult, AthenaError
from .athena_service import AthenaService

logger = logging.getLogger(__name__)


class DiscoverSchemaArgs(BaseModel):
    """Arguments for schema discovery tool."""
    pass


class GetTableSchemaArgs(BaseModel):
    """Arguments for getting table schema."""
    database_name: str = Field(..., min_length=1, description="Name of the database containing the table")
    table_name: str = Field(..., min_length=1, description="Name of the table to inspect")


class ExecuteQueryArgs(BaseModel):
    """Arguments for executing SQL queries."""
    sql: str = Field(..., min_length=1, description="SQL query to execute (SELECT only)")
    database_name: Optional[str] = Field(None, description="Database name (uses default if not specified)")
    limit: int = Field(100, description="Maximum rows to return", ge=1, le=1000)


class GenerateQueryArgs(BaseModel):
    """Arguments for generating queries from natural language prompts."""
    prompt: str = Field(..., min_length=1, description="Natural language description of desired query")
    database_name: Optional[str] = Field(None, description="Database name (uses default if not specified)")


class AthenaMCPServer:
    """MCP Server for AWS Athena data lake querying."""
    
    def __init__(self):
        self.mcp = FastMCP(
            name="athena-mcp-server",
            instructions="AWS Athena data lake querying server providing schema discovery, query execution, and natural language query generation."
        )
        
        # Load configuration from environment
        region = os.getenv("AWS_REGION", "us-east-1")
        s3_bucket = os.getenv("ATHENA_S3_BUCKET")
        s3_prefix = os.getenv("ATHENA_S3_PREFIX", "athena-results/")
        database = os.getenv("ATHENA_DATABASE")
        workgroup = os.getenv("ATHENA_WORKGROUP", "primary")
        
        if not s3_bucket:
            raise ValueError("ATHENA_S3_BUCKET environment variable is required")
        
        self.athena_service = AthenaService(
            region=region,
            s3_bucket=s3_bucket,
            s3_prefix=s3_prefix,
            database=database,
            workgroup=workgroup
        )
        
        self._register_custom_routes()
        self._register_tools()
        self._register_prompts()
    
    def _register_custom_routes(self):
        """Register custom routes for health checks and service info."""
        
        @self.mcp.custom_route("/health", methods=["GET"])
        async def health_check(request: Request) -> JSONResponse:
            """Health check endpoint"""
            return JSONResponse(content={
                "status": "healthy", 
                "service": "athena-mcp-server",
                "aws_region": os.getenv("AWS_REGION", "us-east-1")
            })
        
        @self.mcp.custom_route("/", methods=["GET"])
        async def root(request: Request) -> JSONResponse:
            """Root endpoint with service information."""
            tool_names = [tool.name for tool in self.mcp.tools.values()]
            return JSONResponse(content={
                "service": "Athena MCP Server",
                "version": "1.0.0",
                "transport": "streamable-http",
                "endpoints": {
                    "mcp": "/mcp",
                    "health": "/health"
                },
                "description": "AWS Athena data lake querying server with schema discovery and natural language query generation.",
                "mcp_capabilities": {
                    "tools": tool_names,
                    "prompts": True,
                    "resources": False
                }
            })
    
    def _register_tools(self):
        """Register all Athena tools."""
        
        @self.mcp.tool
        async def discover_schema(ctx: Context, args: DiscoverSchemaArgs) -> SchemaDiscoveryResult:
            """Discover all databases and tables in the data catalog."""
            await ctx.info("Discovering data lake schema...")
            try:
                return await self.athena_service.discover_schema()
            except AthenaError as e:
                await ctx.error(f"Schema discovery failed: {e.message}")
                raise
        
        @self.mcp.tool
        async def get_table_schema(ctx: Context, args: GetTableSchemaArgs) -> TableSchema:
            """Get detailed schema for a specific table including columns and partitions."""
            if not args.database_name.strip():
                await ctx.error("Database name cannot be empty")
                raise ValueError("Database name cannot be empty")
            if not args.table_name.strip():
                await ctx.error("Table name cannot be empty")
                raise ValueError("Table name cannot be empty")
                
            await ctx.info(f"Getting schema for table {args.database_name}.{args.table_name}")
            try:
                return await self.athena_service.get_table_schema(args.database_name, args.table_name)
            except AthenaError as e:
                await ctx.error(f"Failed to get table schema: {e.message}")
                raise
        
        @self.mcp.tool
        async def execute_query(ctx: Context, args: ExecuteQueryArgs) -> QueryResult:
            """Execute SQL queries against the data lake (SELECT queries only)."""
            if not args.sql.strip():
                await ctx.error("SQL query cannot be empty")
                raise ValueError("SQL query cannot be empty")
                
            await ctx.info(f"Executing query on database {args.database_name or 'default'}")
            try:
                sql = args.sql.strip()
                
                # Add LIMIT clause if not present and query doesn't already have one
                if not sql.upper().endswith(f"LIMIT {args.limit}") and "LIMIT" not in sql.upper():
                    sql = f"{sql} LIMIT {args.limit}"
                
                return await self.athena_service.execute_query(sql, args.database_name)
            except AthenaError as e:
                await ctx.error(f"Query execution failed: {e.message}")
                raise
        
        @self.mcp.tool
        async def generate_query(ctx: Context, args: GenerateQueryArgs) -> str:
            """Generate SQL queries from natural language prompts."""
            if not args.prompt.strip():
                await ctx.error("Prompt cannot be empty")
                raise ValueError("Prompt cannot be empty")
                
            await ctx.info(f"Generating query from prompt: {args.prompt[:50]}...")
            try:
                return await self.athena_service.generate_query_from_prompt(args.prompt, args.database_name)
            except AthenaError as e:
                await ctx.error(f"Query generation failed: {e.message}")
                raise
        
        @self.mcp.tool
        async def execute_generated_query(ctx: Context, args: GenerateQueryArgs) -> QueryResult:
            """Generate and execute a query from natural language prompt."""
            if not args.prompt.strip():
                await ctx.error("Prompt cannot be empty")
                raise ValueError("Prompt cannot be empty")
                
            await ctx.info(f"Generating and executing query from prompt: {args.prompt[:50]}...")
            try:
                sql = await self.athena_service.generate_query_from_prompt(args.prompt, args.database_name)
                await ctx.info(f"Generated SQL: {sql}")
                return await self.athena_service.execute_query(sql, args.database_name)
            except AthenaError as e:
                await ctx.error(f"Query generation and execution failed: {e.message}")
                raise
    
    def _register_prompts(self):
        """Register Athena prompts."""
        
        @self.mcp.prompt
        async def athena_query_guide(ctx: Context) -> str:
            """Guide for effective Athena querying and data lake exploration"""
            return """
# AWS Athena Data Lake Query Guide

## Schema Discovery Strategy
- **Start with discovery**: Use discover_schema to understand available databases and tables
- **Table inspection**: Get detailed schemas before querying to understand column types
- **Partition awareness**: Check partition keys for performance optimization

## Query Best Practices
- **Cost optimization**: Use LIMIT clauses to control data scanning costs
- **Partition filtering**: Filter on partition keys when possible for better performance
- **Column selection**: Specify only needed columns instead of SELECT *
- **Data types**: Be aware of column types for proper filtering and aggregation

## Natural Language Querying
- **Be specific**: Describe exactly what data you want to see
- **Include context**: Mention table names or data characteristics when known
- **Start simple**: Begin with basic queries and build complexity gradually

## Performance Considerations
- **Columnar formats**: Parquet and ORC formats scan faster than CSV
- **Compression**: Compressed data reduces scan time and costs
- **File sizes**: Avoid many small files, prefer fewer large files
- **Query patterns**: Use approximate functions for large datasets when exact counts aren't needed
            """.strip()
    
    async def cleanup(self):
        """Clean up resources."""
        await self.athena_service.close()


def create_mcp_server() -> AthenaMCPServer:
    """Create Athena MCP server."""
    return AthenaMCPServer()