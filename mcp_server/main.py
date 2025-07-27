import asyncio
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from .server import create_mcp_server

# Load environment variables from .env file
env_file = Path(__file__).parent.parent / ".env"
if env_file.exists():
    load_dotenv(env_file)
    logger = logging.getLogger(__name__)
    logger.info(f"Loaded environment variables from {env_file}")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration from environment variables
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8001"))


async def main():
    """Main entry point for the Wikipedia MCP server"""
    logger.info(f"Starting Wikipedia MCP Server on {HOST}:{PORT}")
    logger.info("Server capabilities:")
    logger.info("  - Wikipedia article search")
    logger.info("  - Full article content retrieval")
    logger.info("  - Multi-language support")
    logger.info("  - Random article discovery")
    logger.info("  - Article existence checking")
    
    # Create and start the MCP server
    mcp_server = create_mcp_server()
    
    # Use FastMCP's native HTTP transport with stateless_http=True
    try:
        await mcp_server.mcp.run_async(
            transport="http",
            host=HOST,
            port=PORT,
            path="/mcp",
            stateless_http=True
        )
    except Exception as e:
        logger.error(f"Server startup failed: {e}")
        raise
    finally:
        # Cleanup
        await mcp_server.cleanup()


def main_sync():
    """Synchronous entry point for the application"""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down Wikipedia MCP Server...")
    except Exception as e:
        logger.error(f"Application error: {e}")
        raise


if __name__ == "__main__":
    main_sync()