import asyncio
import logging
import re
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from botocore.config import Config

from .models import TableSchema, QueryResult, DatabaseSummary, SchemaDiscoveryResult, AthenaError

logger = logging.getLogger(__name__)


class AthenaService:
    def __init__(
        self,
        region: str,
        s3_bucket: str,
        s3_prefix: str = "athena-results/",
        database: Optional[str] = None,
        workgroup: str = "primary"
    ):
        self._region = region
        self._s3_bucket = s3_bucket
        self._s3_prefix = s3_prefix
        self._database = database
        self._workgroup = workgroup
        
        self._athena_client: Optional[boto3.client] = None
        self._glue_client: Optional[boto3.client] = None
        
        self._config = Config(
            retries={'max_attempts': 3, 'mode': 'adaptive'},
            max_pool_connections=50
        )

    async def _get_athena_client(self) -> boto3.client:
        if self._athena_client is None:
            try:
                self._athena_client = boto3.client('athena', region_name=self._region, config=self._config)
            except NoCredentialsError as e:
                raise AthenaError("AWS credentials not configured") from e
        return self._athena_client

    async def _get_glue_client(self) -> boto3.client:
        if self._glue_client is None:
            try:
                self._glue_client = boto3.client('glue', region_name=self._region, config=self._config)
            except NoCredentialsError as e:
                raise AthenaError("AWS credentials not configured") from e
        return self._glue_client

    async def discover_schema(self) -> SchemaDiscoveryResult:
        try:
            glue_client = await self._get_glue_client()
            
            paginator = glue_client.get_paginator('get_databases')
            databases = []
            total_tables = 0
            
            for page in paginator.paginate():
                for db in page['DatabaseList']:
                    db_name = db['Name']
                    
                    table_paginator = glue_client.get_paginator('get_tables')
                    tables = []
                    
                    for table_page in table_paginator.paginate(DatabaseName=db_name):
                        table_names = [table['Name'] for table in table_page['TableList']]
                        tables.extend(table_names)
                    
                    databases.append(DatabaseSummary(
                        database_name=db_name,
                        table_count=len(tables),
                        tables=tables
                    ))
                    total_tables += len(tables)
            
            return SchemaDiscoveryResult(databases=databases, total_tables=total_tables)
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            raise AthenaError(f"AWS error during schema discovery: {error_code}") from e
        except Exception as e:
            logger.error(f"Unexpected error during schema discovery: {e}")
            raise AthenaError(f"Schema discovery failed: {str(e)}") from e

    async def get_table_schema(self, database_name: str, table_name: str) -> TableSchema:
        if not database_name or not database_name.strip():
            raise AthenaError("Database name cannot be empty")
        if not table_name or not table_name.strip():
            raise AthenaError("Table name cannot be empty")
            
        try:
            glue_client = await self._get_glue_client()
            
            response = glue_client.get_table(DatabaseName=database_name.strip(), Name=table_name.strip())
            table = response['Table']
            
            storage_descriptor = table['StorageDescriptor']
            columns = [
                {
                    'name': col['Name'],
                    'type': col['Type'],
                    'comment': col.get('Comment', '')
                }
                for col in storage_descriptor['Columns']
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
                database_name=table['DatabaseName'],
                columns=columns,
                location=storage_descriptor['Location'],
                input_format=storage_descriptor.get('InputFormat'),
                partition_keys=partition_keys
            )
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'EntityNotFoundException':
                raise AthenaError(f"Table {database_name}.{table_name} not found") from e
            raise AthenaError(f"AWS error getting table schema: {error_code}") from e
        except Exception as e:
            logger.error(f"Unexpected error getting table schema: {e}")
            raise AthenaError(f"Failed to get table schema: {str(e)}") from e

    async def execute_query(self, sql: str, database_name: Optional[str] = None) -> QueryResult:
        if not sql or not sql.strip():
            raise AthenaError("SQL query cannot be empty")
            
        sql = sql.strip()
        if not self._is_safe_query(sql):
            raise AthenaError("Only SELECT queries are allowed")
        
        try:
            athena_client = await self._get_athena_client()
            db_name = database_name or self._database
            
            if not db_name or not db_name.strip():
                raise AthenaError("Database name must be specified")
            
            response = athena_client.start_query_execution(
                QueryString=sql,
                QueryExecutionContext={'Database': db_name.strip()},
                ResultConfiguration={
                    'OutputLocation': f"s3://{self._s3_bucket}/{self._s3_prefix}"
                },
                WorkGroup=self._workgroup
            )
            
            query_id = response['QueryExecutionId']
            return await self._wait_for_query_completion(query_id)
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            raise AthenaError(f"AWS error executing query: {error_code}") from e
        except Exception as e:
            logger.error(f"Unexpected error executing query: {e}")
            raise AthenaError(f"Query execution failed: {str(e)}") from e

    async def generate_query_from_prompt(self, prompt: str, database_name: Optional[str] = None) -> str:
        if not prompt or not prompt.strip():
            raise AthenaError("Prompt cannot be empty")
            
        db_name = database_name or self._database
        if not db_name or not db_name.strip():
            raise AthenaError("Database name required for query generation")
        
        try:
            schema_result = await self.discover_schema()
            target_db = next((db for db in schema_result.databases if db.database_name == db_name.strip()), None)
            
            if not target_db:
                raise AthenaError(f"Database {db_name.strip()} not found")
            
            # Simple query generation based on prompt analysis
            prompt_lower = prompt.lower()
            
            if 'count' in prompt_lower and 'table' in prompt_lower:
                if target_db.tables:
                    table_name = target_db.tables[0]
                    return f"SELECT COUNT(*) as row_count FROM {db_name.strip()}.{table_name}"
            
            if 'show' in prompt_lower and ('table' in prompt_lower or 'schema' in prompt_lower):
                return f"SHOW TABLES IN {db_name.strip()}"
            
            if 'describe' in prompt_lower or 'column' in prompt_lower:
                if target_db.tables:
                    table_name = target_db.tables[0]
                    return f"DESCRIBE {db_name.strip()}.{table_name}"
            
            # Default: select from first available table
            if target_db.tables:
                table_name = target_db.tables[0]
                return f"SELECT * FROM {db_name.strip()}.{table_name} LIMIT 10"
            
            raise AthenaError(f"No tables found in database {db_name.strip()}")
            
        except Exception as e:
            logger.error(f"Error generating query from prompt: {e}")
            raise AthenaError(f"Query generation failed: {str(e)}") from e

    async def _wait_for_query_completion(self, query_id: str) -> QueryResult:
        athena_client = await self._get_athena_client()
        
        max_wait_time = timedelta(minutes=10)
        start_time = datetime.now()
        
        while datetime.now() - start_time < max_wait_time:
            response = athena_client.get_query_execution(QueryExecutionId=query_id)
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
            
            await asyncio.sleep(1)
        
        return QueryResult(
            query_id=query_id,
            status='TIMEOUT',
            error_message='Query execution timeout'
        )

    async def _get_query_results(self, query_id: str, execution: Dict[str, Any]) -> QueryResult:
        athena_client = await self._get_athena_client()
        
        try:
            results_response = athena_client.get_query_results(QueryExecutionId=query_id)
            result_set = results_response['ResultSet']
            
            column_info = []
            rows = []
            
            if 'ColumnInfos' in result_set:
                column_info = [
                    {
                        'name': col['Name'],
                        'type': col['Type'],
                        'label': col.get('Label', col['Name'])
                    }
                    for col in result_set['ColumnInfos']
                ]
            
            if 'Rows' in result_set and len(result_set['Rows']) > 1:
                header_row = result_set['Rows'][0]['Data']
                data_rows = result_set['Rows'][1:]
                
                for row in data_rows:
                    row_dict = {}
                    for i, cell in enumerate(row['Data']):
                        col_name = header_row[i].get('VarCharValue', f'col_{i}')
                        row_dict[col_name] = cell.get('VarCharValue')
                    rows.append(row_dict)
            
            stats = execution.get('Statistics', {})
            
            return QueryResult(
                query_id=query_id,
                status='SUCCEEDED',
                rows=rows,
                column_info=column_info,
                data_scanned_bytes=stats.get('DataScannedInBytes'),
                execution_time_ms=stats.get('EngineExecutionTimeInMillis')
            )
            
        except Exception as e:
            logger.error(f"Error getting query results: {e}")
            return QueryResult(
                query_id=query_id,
                status='ERROR',
                error_message=f"Failed to retrieve results: {str(e)}"
            )

    def _is_safe_query(self, sql: str) -> bool:
        if not sql or not sql.strip():
            return False
            
        dangerous_keywords = ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'CREATE', 'ALTER', 'TRUNCATE']
        sql_upper = sql.upper().strip()
        
        # Must start with SELECT or be a SHOW/DESCRIBE command
        if not (sql_upper.startswith('SELECT') or sql_upper.startswith('SHOW') or sql_upper.startswith('DESCRIBE')):
            return False
            
        return not any(keyword in sql_upper for keyword in dangerous_keywords)

    async def close(self):
        self._athena_client = None
        self._glue_client = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()