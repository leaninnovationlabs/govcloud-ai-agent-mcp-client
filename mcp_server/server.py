import logging
from typing import Optional, List
from pydantic import BaseModel, Field

from fastmcp import FastMCP, Context
from starlette.requests import Request
from starlette.responses import JSONResponse

from .models import (
    WikipediaSearchResult, WikipediaArticle, WikipediaError,
    WikipediaSearchResponse
)
from .wikipedia_service import WikipediaService

logger = logging.getLogger(__name__)

# ==============================================================================
# Pydantic Models for Tool Arguments
# ==============================================================================
# By defining tool arguments with Pydantic models, FastMCP can automatically
# generate the correct JSON schema for each tool. This is the recommended
# approach for ensuring type safety and clear schema definitions.

class SearchWikipediaArgs(BaseModel):
    """Arguments for the search_wikipedia tool."""
    query: str = Field(..., description="The search query for Wikipedia.")
    limit: int = Field(10, description="Maximum number of search results to return.")
    lang: str = Field("en", description="The Wikipedia language edition (e.g., 'en', 'es').")

class GetWikipediaArticleArgs(BaseModel):
    """Arguments for tools that operate on a specific article title."""
    title: str = Field(..., description="The exact title of the Wikipedia article.")
    lang: str = Field("en", description="The Wikipedia language edition (e.g., 'en', 'es').")

class RandomWikipediaArticleArgs(BaseModel):
    """Arguments for the random_wikipedia_article tool."""
    lang: str = Field("en", description="The Wikipedia language edition for the random article.")


# ==============================================================================
# Wikipedia MCP Server
# ==============================================================================

class WikipediaMCPServer:
    """Simple MCP Server for Wikipedia integration without authentication."""
    
    def __init__(self):
        self.mcp = FastMCP(
            name="wikipedia-mcp-server",
            instructions="Wikipedia integration server providing article search, content retrieval, and multi-language support."
        )
        self.wikipedia_service = WikipediaService()
        
        # Register custom routes and tools
        self._register_custom_routes()
        self._register_tools()
        self._register_prompts()
    
    def _register_custom_routes(self):
        """Register custom routes for health checks."""
        
        @self.mcp.custom_route("/health", methods=["GET"])
        async def health_check(request: Request) -> JSONResponse:
            """Health check endpoint"""
            return JSONResponse(content={"status": "healthy", "service": "wikipedia-mcp-server"})
        
        @self.mcp.custom_route("/", methods=["GET"])
        async def root(request: Request) -> JSONResponse:
            """Root endpoint with service information."""
            # Dynamically get the list of registered tool names
            tool_names = [tool.name for tool in self.mcp.tools.values()]
            return JSONResponse(content={
                "service": "Wikipedia MCP Server",
                "version": "2.0.0",
                "transport": "streamable-http",
                "endpoints": {
                    "mcp": "/mcp",
                    "health": "/health"
                },
                "description": "Simple Wikipedia MCP server for testing with multiple MCP servers.",
                "mcp_capabilities": {
                    # Provide the actual list of tool names
                    "tools": tool_names,
                    "prompts": True,
                    "resources": False
                }
            })
    
    def _register_tools(self):
        """
        Register all Wikipedia tools.
        
        By using a Pydantic model as a type hint for an argument, FastMCP
        automatically infers the input schema.
        """
        
        @self.mcp.tool
        async def search_wikipedia(ctx: Context, args: SearchWikipediaArgs) -> WikipediaSearchResponse:
            """Search Wikipedia articles by query."""
            await ctx.info(f"Searching Wikipedia for: {args.query} (lang: {args.lang})")
            return await self.wikipedia_service.search_articles(args.query, args.limit, args.lang)
        
        @self.mcp.tool
        async def get_wikipedia_article(ctx: Context, args: GetWikipediaArticleArgs) -> WikipediaArticle:
            """Get full Wikipedia article content by its exact title."""
            await ctx.info(f"Fetching Wikipedia article: {args.title} (lang: {args.lang})")
            return await self.wikipedia_service.get_article(args.title, args.lang)
        
        @self.mcp.tool
        async def get_article_summary(ctx: Context, args: GetWikipediaArticleArgs) -> str:
            """Get the summary (introduction) of a Wikipedia article by its exact title."""
            await ctx.info(f"Fetching Wikipedia summary: {args.title} (lang: {args.lang})")
            return await self.wikipedia_service.get_article_summary(args.title, args.lang)
        
        @self.mcp.tool
        async def random_wikipedia_article(ctx: Context, args: RandomWikipediaArticleArgs) -> WikipediaArticle:
            """Get a random Wikipedia article."""
            await ctx.info(f"Fetching random Wikipedia article (lang: {args.lang})")
            return await self.wikipedia_service.get_random_article(args.lang)
        
        @self.mcp.tool
        async def check_article_exists(ctx: Context, args: GetWikipediaArticleArgs) -> bool:
            """Check if a Wikipedia article with the given title exists."""
            await ctx.info(f"Checking if Wikipedia article exists: {args.title} (lang: {args.lang})")
            return await self.wikipedia_service.article_exists(args.title, args.lang)
    
    def _register_prompts(self):
        """Register Wikipedia prompts."""
        
        @self.mcp.prompt
        async def wikipedia_research_guide(ctx: Context) -> str:
            """Guide for conducting Wikipedia research"""
            return """
# Wikipedia Research Best Practices

## Search Strategy
- **Broad to Specific**: Start with general terms, then narrow down
- **Alternative Terms**: Try different spellings and synonyms
- **Language Variants**: Consider searching in multiple languages
- **Related Topics**: Explore linked articles for deeper understanding

## Article Evaluation
- **Currency**: Check when the article was last updated
- **Sources**: Look for reliable citations and references
- **Completeness**: Assess if major aspects are covered
- **Neutrality**: Consider potential bias in presentation

## Multi-language Research
- **Cross-reference**: Compare information across language versions
- **Cultural Context**: Different languages may provide unique insights
- **Translation**: Use summaries to understand content in other languages

## Information Gathering
- **Take Notes**: Extract key facts and quotes
- **Track Sources**: Note the Wikipedia URLs and edit dates
- **Verify**: Cross-check important claims with cited sources
- **Explore Links**: Follow relevant internal links for broader context
            """.strip()
    
    async def cleanup(self):
        """Clean up resources."""
        await self.wikipedia_service.close()


def create_mcp_server() -> WikipediaMCPServer:
    """Create Wikipedia MCP server."""
    return WikipediaMCPServer()