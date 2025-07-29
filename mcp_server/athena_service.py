import asyncio
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import json
import re 

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from botocore.config import Config
import instructor
from pydantic import BaseModel, Field

from .models import (
    TableSchema, QueryResult, DatabaseSummary, SchemaDiscoveryResult, 
    AthenaError, SQLQuery, SchemaContext, DatabaseInfo
)

logger = logging.getLogger(__name__)


class QueryGenerationRequest(BaseModel):
    prompt: str = Field(..., description="Natural language query request")
    schema_context: SchemaContext = Field(..., description="Database schema context for query generation")
    query_hints: List[str] = Field(default_factory=list, description="Additional hints for query generation")
    safety_mode: bool = Field(True, description="Enforce read-only queries")


class AthenaService:
    def __init__(
        self,
        region: str,
        s3_bucket: str,
        s3_prefix: str = "athena-results/",
        database: Optional[str] = None,
        workgroup: str = "primary",
        bedrock_model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0",
        bedrock_region: Optional[str] = None
    ):
        self._region = region
        self._s3_bucket = s3_bucket
        self._s3_prefix = s3_prefix.rstrip('/') + '/'
        self._database = database
        self._workgroup = workgroup
        self._bedrock_model_id = bedrock_model_id
        self._bedrock_region = bedrock_region or region
        
        self._athena_client: Optional[boto3.client] = None
        self._glue_client: Optional[boto3.client] = None
        self._instructor_client: Optional[instructor.Instructor] = None
        
        self._config = Config(
            retries={'max_attempts': 3, 'mode': 'adaptive'},
            max_pool_connections=50
        )
        
        self._schema_cache: Dict[str, SchemaContext] = {}
        self._cache_ttl = 300

    async def _get_athena_client(self) -> boto3.client:
        if self._athena_client is None:
            try:
                self._athena_client = boto3.client('athena', region_name=self._region, config=self._config)
            except NoCredentialsError:
                raise AthenaError("AWS credentials not configured", error_code="NO_CREDENTIALS")
        return self._athena_client

    async def _get_glue_client(self) -> boto3.client:
        if self._glue_client is None:
            try:
                self._glue_client = boto3.client('glue', region_name=self._region, config=self._config)
            except NoCredentialsError:
                raise AthenaError("AWS credentials not configured", error_code="NO_CREDENTIALS")
        return self._glue_client

    async def _get_instructor_client(self) -> instructor.Instructor:
        if self._instructor_client is None:
            try:
                # Use the simplified from_provider approach
                # This automatically handles AWS credential detection and region configuration
                self._instructor_client = instructor.from_bedrock(
                    boto3.client('bedrock-runtime', region_name=self._region, config=self._config),
                    # region_name=self._bedrock_region
                )
            except Exception as e:
                logger.error(f"Failed to initialize Instructor client: {e}")
                raise AthenaError(f"Bedrock initialization failed: {str(e)}", error_code="BEDROCK_INIT_ERROR")
        return self._instructor_client

    async def discover_schema(self) -> SchemaDiscoveryResult:
        try:
            glue_client = await self._get_glue_client()
            
            databases = []
            total_tables = 0
            
            paginator = glue_client.get_paginator('get_databases')
            pages = await asyncio.to_thread(
                lambda: list(paginator.paginate())
            )
            
            for page in pages:
                for db in page.get('DatabaseList', []):
                    db_info = DatabaseInfo(
                        name=db['Name'],
                        description=db.get('Description'),
                        location_uri=db.get('LocationUri'),
                        parameters=db.get('Parameters', {}),
                        create_time=db.get('CreateTime')
                    )
                    
                    # Fetch full table schemas instead of just names
                    table_schemas = await self._get_all_table_schemas_for_db(db['Name'])
                    
                    databases.append(DatabaseSummary(
                        database_name=db['Name'],
                        table_count=len(table_schemas),
                        tables=table_schemas,
                        info=db_info
                    ))
                    total_tables += len(table_schemas)
            
            return SchemaDiscoveryResult(
                databases=databases, 
                total_tables=total_tables,
                default_database=self._database
            )
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            raise AthenaError(f"AWS error during schema discovery: {error_code}", error_code=error_code)
        except Exception as e:
            logger.error(f"Unexpected error during schema discovery: {e}")
            raise AthenaError(f"Schema discovery failed: {str(e)}", error_code="DISCOVERY_ERROR")

    async def _get_all_table_schemas_for_db(self, database_name: str) -> List[TableSchema]:
        """Gets the full TableSchema for all tables in a given database concurrently."""
        try:
            table_names = await self._get_database_tables(database_name)
            
            # Concurrently fetch the schema for each table
            tasks = [self.get_table_schema(database_name, table_name) for table_name in table_names]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Filter out any exceptions that may have occurred, logging them for visibility
            table_schemas = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.warning(f"Failed to get schema for table {database_name}.{table_names[i]}: {result}")
                else:
                    table_schemas.append(result)
            
            return table_schemas
        except Exception as e:
            logger.error(f"Error getting all table schemas for database {database_name}: {e}")
            return [] # Return empty list on failure to avoid breaking the whole discovery process

    async def _get_database_tables(self, database_name: str) -> List[str]:
        glue_client = await self._get_glue_client()
        tables = []
        
        paginator = glue_client.get_paginator('get_tables')
        pages = await asyncio.to_thread(
            lambda: list(paginator.paginate(DatabaseName=database_name))
        )
        
        for page in pages:
            table_names = [table['Name'] for table in page.get('TableList', [])]
            tables.extend(table_names)
        
        return sorted(tables)

    async def get_table_schema(self, database_name: str, table_name: str) -> TableSchema:
        database_name = database_name.strip()
        table_name = table_name.strip()
        
        if not database_name:
            raise AthenaError("Database name cannot be empty", error_code="INVALID_INPUT")
        if not table_name:
            raise AthenaError("Table name cannot be empty", error_code="INVALID_INPUT")
            
        try:
            glue_client = await self._get_glue_client()
            
            response = await asyncio.to_thread(
                glue_client.get_table,
                DatabaseName=database_name,
                Name=table_name
            )
            table = response['Table']
            
            storage_descriptor = table.get('StorageDescriptor', {})
            columns = [
                {
                    'name': col['Name'],
                    'type': col['Type'],
                    'comment': col.get('Comment', '')
                }
                for col in storage_descriptor.get('Columns', [])
            ]
            
            partition_keys = [
                {
                    'name': pk['Name'],
                    'type': pk['Type'],
                    'comment': pk.get('Comment', '')
                }
                for pk in table.get('PartitionKeys', [])
            ]
            
            return TableSchema(
                table_name=table['Name'],
                database_name=database_name,
                columns=columns,
                location=storage_descriptor.get('Location', ''),
                input_format=storage_descriptor.get('InputFormat'),
                output_format=storage_descriptor.get('OutputFormat'),
                partition_keys=partition_keys,
                table_type=table.get('TableType'),
                created_time=table.get('CreateTime'),
                last_access_time=table.get('LastAccessTime'),
                parameters=table.get('Parameters', {})
            )
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'EntityNotFoundException':
                raise AthenaError(f"Table {database_name}.{table_name} not found", error_code=error_code)
            raise AthenaError(f"AWS error getting table schema: {error_code}", error_code=error_code)

    async def _get_schema_context(self, database_name: str) -> SchemaContext:
        cache_key = f"schema_{database_name}"
        if cache_key in self._schema_cache:
            return self._schema_cache[cache_key]
        
        tables = await self._get_database_tables(database_name)
        table_schemas = []
        partition_columns = set()
        
        for table_name in tables[:10]:  # Limit to first 10 tables for context
            try:
                schema = await self.get_table_schema(database_name, table_name)
                table_schemas.append(schema)
                for pk in schema.partition_keys:
                    partition_columns.add(pk['name'])
            except Exception as e:
                logger.warning(f"Failed to get schema for {database_name}.{table_name}: {e}")
        
        context = SchemaContext(
            database_name=database_name,
            tables=table_schemas,
            partition_columns=list(partition_columns)
        )
        
        self._schema_cache[cache_key] = context
        return context

    async def generate_query_from_prompt(self, prompt: str, database_name: Optional[str] = None) -> str:
        prompt = prompt.strip()
        if not prompt:
            raise AthenaError("Prompt cannot be empty", error_code="INVALID_INPUT")
            
        db_name = database_name or self._database
        if not db_name:
            raise AthenaError("Database name required for query generation", error_code="INVALID_INPUT")
        
        try:
            instructor_client = await self._get_instructor_client()
            schema_context = await self._get_schema_context(db_name)
            
            request = QueryGenerationRequest(
                prompt=prompt,
                schema_context=schema_context,
                query_hints=[
                    "Use partition columns in WHERE clauses when possible",
                    "Always include LIMIT clause for safety",
                    "Prefer columnar formats like Parquet or ORC",
                    "Use approximate functions for large aggregations when exact counts aren't needed",
                    "Don't forget spaces around SQL keywords",
                    "backquoted identifiers are not supported; use double quotes to quote identifiers",
                    "remember that this is Athena SQL and not standard SQL, so some syntax may differ",
                    "assume it's all on one line unless specified otherwise",
                    "assume it's all on one line unless specified otherwise. If I get no spaces I will jump off a bridge",
                ]
            )
            
            logger.info(f"Generating SQL query: {request}")   

            system_prompt = self._build_sql_generation_prompt(request)

            logger.info(f"SQL generation system prompt: {system_prompt}")
            
            # Since Bedrock doesn't support async, wrap the sync call
            def generate_sql():
                return instructor_client.chat.completions.create(
                    model=self._bedrock_model_id,
                    messages=[
                        {"role": "user", "content": f"{system_prompt}\n\nGenerate an AWS Athena SQL query for: {prompt}"}
                    ],
                    response_model=SQLQuery,
                    max_tokens=1000,
                    temperature=0.1
                )
            
            response = await asyncio.to_thread(generate_sql)
            
            logger.info(f"SQL generation response: {response}")

            if response.warnings:
                logger.warning(f"Query generation warnings: {response.warnings}")

            cleaned_sql = re.sub(r'(\w)FROM', r'\1 FROM', response.sql)

            return cleaned_sql
            
        except Exception as e:
            logger.error(f"Error generating query from prompt: {e}")
            raise AthenaError(f"Query generation failed: {str(e)}", error_code="GENERATION_ERROR")

    def _build_sql_generation_prompt(self, request: QueryGenerationRequest) -> str:
        tables_info = []
        for table in request.schema_context.tables[:5]:
            cols = [f"{c['name']} ({c['type']})" for c in table.columns[:15]]
            parts = [f"{p['name']} ({p['type']})" for p in table.partition_keys]
            tables_info.append(
                f"Table: {table.table_name}\n"
                f"  Columns: {', '.join(cols)}\n"
                f"  Partitions: {', '.join(parts) if parts else 'None'}\n"
                f"  Location: {table.location}"
            )
        
        return f"""You are an AWS Athena SQL expert. Generate optimized queries for S3-based data lakes.

Database: {request.schema_context.database_name}
Available Tables:
{chr(10).join(tables_info)}

Important Guidelines:
- You MUST use the column names provided in the schema. Do NOT invent or guess column names. If a column you need is not in the schema, you should indicate that the query cannot be completed.
- Do not include the database name in the table name (e.g., use `vessels` not `maritime_shipping_db.vessels`)
- If the schema is not default, the schema might be the database name
- Always include a LIMIT clause to prevent excessive data scanning, unless the user explicitly asks for all data.
- Do not include the database name in the table name (e.g., use `vessels` not `maritime_shipping_db.vessels`)
- Include partition filters when available to reduce scan costs
- Add LIMIT clause to prevent excessive data scanning
- Use columnar predicate pushdown when possible
- Prefer approximate aggregation functions for large datasets
- Consider using WITH clauses for complex queries
- Escape reserved keywords with backticks

Query Requirements:
- Must be a valid SELECT query (no DDL/DML operations)
- Optimize for cost by minimizing data scanned
- Include meaningful column aliases
- Add comments for complex logic

EXAMPLY SUCCESSFUL QUERY:

SELECT f.food_type, f.quantity, f.unit, f.storage_type, f.expiry_date 
FROM food_inventory f
JOIN shipments s ON f.shipment_id = s.shipment_id
JOIN vessels v ON s.vessel_id = v.vessel_id
WHERE v.vessel_name = 'Tidal Surge' AND s.status = 'In Transit'
ORDER BY f.expiry_date ASC
LIMIT 100

Additional Hints:
{chr(10).join(f"- {hint}" for hint in request.query_hints)}
"""

    async def execute_query(self, sql: str, database_name: Optional[str] = None) -> QueryResult:
        logger.info(f"Executing SQL query: {sql}")
        sql = sql.strip()
        if not sql:
            raise AthenaError("SQL query cannot be empty", error_code="INVALID_INPUT")
            
        if not self._is_safe_query(sql):
            raise AthenaError("Only SELECT queries are allowed", error_code="UNSAFE_QUERY")
        
        logger.info(f"cleaned SQL query: {sql}")

        try:
            athena_client = await self._get_athena_client()
            db_name = database_name or self._database
            
            if not db_name:
                raise AthenaError("Database name must be specified", error_code="INVALID_INPUT")
            
            output_location = f"s3://{self._s3_bucket}/{self._s3_prefix}"
            
            response = await asyncio.to_thread(
                athena_client.start_query_execution,
                QueryString=sql,
                QueryExecutionContext={'Database': db_name.strip()},
                ResultConfiguration={'OutputLocation': output_location},
                WorkGroup=self._workgroup
            )
            
            query_id = response['QueryExecutionId']
            return await self._wait_for_query_completion(query_id)
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            raise AthenaError(f"AWS error executing query: {error_code}", error_code=error_code)

    async def _wait_for_query_completion(self, query_id: str) -> QueryResult:
        athena_client = await self._get_athena_client()
        
        max_attempts = 300
        for attempt in range(max_attempts):
            response = await asyncio.to_thread(
                athena_client.get_query_execution,
                QueryExecutionId=query_id
            )
            
            execution = response['QueryExecution']
            status = execution['Status']['State']
            
            if status == 'SUCCEEDED':
                return await self._get_query_results(query_id, execution)
            elif status in ['FAILED', 'CANCELLED']:
                error_msg = execution['Status'].get('StateChangeReason', 'Unknown error')
                return QueryResult(
                    query_id=query_id,
                    status=status,
                    error_message=error_msg
                )
            
            await asyncio.sleep(1 if attempt < 10 else 2)
        
        return QueryResult(
            query_id=query_id,
            status='FAILED',
            error_message='Query execution timeout'
        )

    async def _get_query_results(self, query_id: str, execution: Dict[str, Any]) -> QueryResult:
        athena_client = await self._get_athena_client()
        
        try:
            results_response = await asyncio.to_thread(
                athena_client.get_query_results,
                QueryExecutionId=query_id,
                MaxResults=1000
            )
            
            result_set = results_response['ResultSet']
            
            column_info = [
                {
                    'name': col['Name'],
                    'type': col['Type'],
                    'label': col.get('Label', col['Name'])
                }
                for col in result_set.get('ColumnInfo', [])
            ]
            
            rows = []
            if 'Rows' in result_set and len(result_set['Rows']) > 1:
                header_row = result_set['Rows'][0]['Data']
                column_names = [cell.get('VarCharValue', f'col_{i}') for i, cell in enumerate(header_row)]
                
                for row in result_set['Rows'][1:]:
                    row_dict = {}
                    for i, cell in enumerate(row.get('Data', [])):
                        if i < len(column_names):
                            row_dict[column_names[i]] = cell.get('VarCharValue')
                    rows.append(row_dict)
            
            stats = execution.get('Statistics', {})
            result_config = execution.get('ResultConfiguration', {})
            
            return QueryResult(
                query_id=query_id,
                status='SUCCEEDED',
                rows=rows,
                column_info=column_info,
                data_scanned_bytes=stats.get('DataScannedInBytes'),
                execution_time_ms=stats.get('EngineExecutionTimeInMillis'),
                output_location=result_config.get('OutputLocation')
            )
            
        except Exception as e:
            logger.error(f"Error getting query results: {e}")
            return QueryResult(
                query_id=query_id,
                status='FAILED',
                error_message=f"Failed to retrieve results: {str(e)}"
            )

    def _is_safe_query(self, sql: str) -> bool:
    
        dangerous_patterns = [
            'DROP', 'DELETE', 'UPDATE', 'INSERT', 'CREATE', 'ALTER', 
            'TRUNCATE', 'GRANT', 'REVOKE', 'MSCK', 'REFRESH'
        ]
        
        sql_normalized = re.sub(r'--.*$', '', sql, flags=re.MULTILINE)
        sql_normalized = re.sub(r'/\*.*?\*/', '', sql_normalized, flags=re.DOTALL)
        
        for pattern in dangerous_patterns:
            if re.search(rf'\b{pattern}\b', sql_normalized, re.IGNORECASE):
                return False
        
        return True

    async def close(self):
        self._athena_client = None
        self._glue_client = None
        self._instructor_client = None
        self._schema_cache.clear()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
