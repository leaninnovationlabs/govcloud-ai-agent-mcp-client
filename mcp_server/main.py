import asyncio
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from .server import create_mcp_server

env_file = Path(__file__).parent.parent / "mcp_server/.env"
if env_file.exists():
    load_dotenv(env_file)
    logger = logging.getLogger(__name__)
    logger.info(f"Loaded environment variables from {env_file}")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8001"))


async def main():
    """Main entry point for the Athena MCP server"""
    logger.info(f"Starting Athena MCP Server on {HOST}:{PORT}")
    logger.info("Server capabilities:")
    logger.info("  - Data lake schema discovery")
    logger.info("  - SQL query execution via Athena")
    logger.info("  - Natural language query generation")
    logger.info("  - Table metadata inspection")
    logger.info(f"  - AWS Region: {os.getenv('AWS_REGION', 'us-east-1')}")
    logger.info(f"  - S3 Bucket: {os.getenv('ATHENA_S3_BUCKET', 'Not configured')}")
    
    try:
        mcp_server = create_mcp_server()
        
        await mcp_server.mcp.run_async(
            transport="http",
            host=HOST,
            port=PORT,
            path="/mcp",
            stateless_http=True
        )
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        raise
    except Exception as e:
        logger.error(f"Server startup failed: {e}")
        raise
    finally:
        if 'mcp_server' in locals():
            await mcp_server.cleanup()


def main_sync():
    """Synchronous entry point for the application"""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down Athena MCP Server...")
    except Exception as e:
        logger.error(f"Application error: {e}")
        raise


if __name__ == "__main__":
    main_sync()