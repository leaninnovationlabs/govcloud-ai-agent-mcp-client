from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class TableSchema(BaseModel):
    model_config = ConfigDict(frozen=True)
    
    table_name: str = Field(..., description="Name of the table")
    database_name: str = Field(..., description="Database containing the table")
    columns: List[Dict[str, str]] = Field(..., description="Column definitions with name, type, and optional comment")
    location: str = Field(..., description="S3 location of the table data")
    input_format: Optional[str] = Field(None, description="Input format of the table data")
    partition_keys: List[Dict[str, str]] = Field(default_factory=list, description="Partition key definitions")


class QueryResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    
    query_id: str = Field(..., description="Athena query execution ID")
    status: str = Field(..., description="Query execution status")
    rows: Optional[List[Dict[str, Any]]] = Field(None, description="Query result rows")
    column_info: Optional[List[Dict[str, str]]] = Field(None, description="Column metadata")
    data_scanned_bytes: Optional[int] = Field(None, description="Amount of data scanned")
    execution_time_ms: Optional[int] = Field(None, description="Query execution time in milliseconds")
    error_message: Optional[str] = Field(None, description="Error message if query failed")


class DatabaseSummary(BaseModel):
    model_config = ConfigDict(frozen=True)
    
    database_name: str = Field(..., description="Database name")
    table_count: int = Field(..., description="Number of tables in database")
    tables: List[str] = Field(..., description="List of table names")


class SchemaDiscoveryResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    
    databases: List[DatabaseSummary] = Field(..., description="Available databases")
    total_tables: int = Field(..., description="Total number of tables across all databases")


class AthenaError(Exception):
    def __init__(self, message: str, query_id: Optional[str] = None):
        super().__init__(message)
        self.message = message
        self.query_id = query_id