from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime


class TableSchema(BaseModel):
    model_config = ConfigDict(frozen=True)
    
    table_name: str = Field(..., description="Name of the table")
    database_name: str = Field(..., description="Database containing the table")
    columns: List[Dict[str, str]] = Field(..., description="Column definitions with name, type, and optional comment")
    location: str = Field(..., description="S3 location of the table data")
    input_format: Optional[str] = Field(None, description="Input format of the table data")
    output_format: Optional[str] = Field(None, description="Output format of the table data")
    partition_keys: List[Dict[str, str]] = Field(default_factory=list, description="Partition key definitions")
    table_type: Optional[str] = Field(None, description="Type of table (EXTERNAL_TABLE, MANAGED_TABLE, etc)")
    created_time: Optional[datetime] = Field(None, description="Table creation timestamp")
    last_access_time: Optional[datetime] = Field(None, description="Last access timestamp")
    parameters: Dict[str, str] = Field(default_factory=dict, description="Table parameters")


class QueryResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    
    query_id: str = Field(..., description="Athena query execution ID")
    status: Literal["QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED"] = Field(..., description="Query execution status")
    rows: Optional[List[Dict[str, Any]]] = Field(None, description="Query result rows")
    column_info: Optional[List[Dict[str, str]]] = Field(None, description="Column metadata")
    data_scanned_bytes: Optional[int] = Field(None, description="Amount of data scanned")
    execution_time_ms: Optional[int] = Field(None, description="Query execution time in milliseconds")
    error_message: Optional[str] = Field(None, description="Error message if query failed")
    output_location: Optional[str] = Field(None, description="S3 location of query results")


class DatabaseInfo(BaseModel):
    model_config = ConfigDict(frozen=True)
    
    name: str = Field(..., description="Database name")
    description: Optional[str] = Field(None, description="Database description")
    location_uri: Optional[str] = Field(None, description="Database location URI")
    parameters: Dict[str, str] = Field(default_factory=dict, description="Database parameters")
    create_time: Optional[datetime] = Field(None, description="Database creation timestamp")


class DatabaseSummary(BaseModel):
    model_config = ConfigDict(frozen=True)
    
    database_name: str = Field(..., description="Database name")
    table_count: int = Field(..., description="Number of tables in database")
    tables: List[TableSchema] = Field(..., description="List of table schemas")
    info: Optional[DatabaseInfo] = Field(None, description="Detailed database information")


class SchemaDiscoveryResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    
    databases: List[DatabaseSummary] = Field(..., description="Available databases")
    total_tables: int = Field(..., description="Total number of tables across all databases")
    default_database: Optional[str] = Field(None, description="Default database if configured")


class SQLQuery(BaseModel):
    sql: str = Field(..., description="Generated SQL query")
    explanation: str = Field(..., description="Natural language explanation of what the query does")
    estimated_scan_size: Optional[str] = Field(None, description="Estimated data scan size")
    warnings: List[str] = Field(default_factory=list, description="Any warnings about the query")
    optimization_hints: List[str] = Field(default_factory=list, description="Query optimization suggestions")


class SchemaContext(BaseModel):
    database_name: str
    tables: List[TableSchema]
    total_size_bytes: Optional[int] = None
    partition_columns: List[str] = Field(default_factory=list)


class AthenaError(Exception):
    def __init__(self, message: str, query_id: Optional[str] = None, error_code: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.query_id = query_id
        self.error_code = error_code