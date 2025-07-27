from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration using Pydantic v2 settings."""
    
    # Database Configuration
    database_url: str = Field(
        default="sqlite+aiosqlite:///./chat.db",
        description="Database connection URL"
    )
    
    # API Configuration
    api_title: str = Field(
        default="GovCloud AI Agent API",
        description="API title"
    )
    api_version: str = Field(
        default="1.0.0",
        description="API version"
    )
    
    # AWS Bedrock Configuration
    aws_region: str = Field(
        default="us-east-1",
        description="AWS region for Bedrock (uses AWS credential chain for authentication)"
    )
    
    # Claude Model Configuration
    claude_model_id: str = Field(
        default="anthropic.claude-3-5-sonnet-20241022-v2:0",
        description="Claude model ID for Bedrock"
    )
    
    # MCP Server Configuration
    mcp_server_url: str = Field(
        default="http://localhost:8001",
        description="MCP server URL for tool discovery and execution"
    )
    mcp_timeout: float = Field(
        default=30.0,
        description="MCP request timeout in seconds"
    )
    
    # Application Configuration
    app_name: str = Field(
        default="GovCloud AI Agent",
        description="Application name"
    )
    debug: bool = Field(
        default=False,
        description="Enable debug mode"
    )
    
    # Logging Configuration
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )
    log_mode: str = Field(
        default="LOCAL",
        description="Logging mode (LOCAL for development, JSON for production)"
    )
    
    # Logfire Configuration
    logfire_token: str = Field(
        default="",
        description="Logfire token for observability and monitoring"
    )
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False
    }


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()


# Global settings instance
settings = get_settings() 