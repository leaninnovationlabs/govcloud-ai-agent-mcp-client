from contextlib import asynccontextmanager

import logfire
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncEngine

from .agent.routes import router as agent_router
from .conversation.routes import router as conversation_router
from .core.config import settings
from .core.exceptions import BusinessLogicError, NotFoundError
from .core.response import APIResponse
from .database.session import Base, engine
from .util.logging import configure_logging, get_logger
from .util.middleware import LoggingMiddleware

# Configure Logfire before other imports
if settings.logfire_token:
    logfire.configure(token=settings.logfire_token)
    logfire.instrument_pydantic_ai()

# Configure structured logging before creating the app
configure_logging(log_level=settings.log_level, log_mode=settings.log_mode)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application startup initiated")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialization completed")
    yield
    logger.info("Application shutdown initiated")
    await engine.dispose()
    logger.info("Application shutdown completed")

origins = ["http://localhost:5173"]

app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    lifespan=lifespan,
)

app.add_middleware(CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add logging middleware
app.add_middleware(LoggingMiddleware)

logger.info("FastAPI application initialized", 
           title=settings.api_title, 
           version=settings.api_version,
           log_level=settings.log_level,
           log_mode=settings.log_mode)


@app.exception_handler(NotFoundError)
async def not_found_exception_handler(request: Request, exc: NotFoundError) -> JSONResponse:
    logger.warning(
        "Not found error occurred",
        error_code=exc.code,
        error_message=exc.message,
        path=request.url.path,
        method=request.method
    )
    response = APIResponse.error_response(exc.code, exc.message)
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content=response.model_dump(),
    )


@app.exception_handler(BusinessLogicError)
async def business_logic_exception_handler(request: Request, exc: BusinessLogicError) -> JSONResponse:
    logger.warning(
        "Business logic error occurred",
        error_code=exc.code,
        error_message=exc.message,
        path=request.url.path,
        method=request.method
    )
    response = APIResponse.error_response(exc.code, exc.message)
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=response.model_dump(),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [f"{error['loc'][-1]}: {error['msg']}" for error in exc.errors()]
    logger.warning(
        "Request validation error occurred",
        validation_errors=errors,
        path=request.url.path,
        method=request.method,
        error_count=len(errors)
    )
    response = APIResponse.validation_error_response(errors)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=response.model_dump(),
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "Unhandled exception occurred",
        exc_info=exc,
        path=request.url.path,
        method=request.method,
        error_type=type(exc).__name__,
        error_message=str(exc)
    )
    response = APIResponse.error_response(
        "INTERNAL_SERVER_ERROR",
        "An unexpected error occurred",
        str(exc) if settings.debug else None
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=response.model_dump(),
    )


app.include_router(conversation_router, prefix="/conversations", tags=["conversations"])
app.include_router(agent_router, prefix="", tags=["chat"])  # Remove prefix so /chat route works directly

logger.info("API routes registered successfully")


@app.get("/", response_model=APIResponse[dict])
async def root() -> APIResponse[dict]:
    """API root endpoint with basic service information."""
    logger.debug("Root endpoint accessed")
    return APIResponse.success_response({
        "message": "GovCloud AI Agent API",
        "version": settings.api_version,
        "status": "operational"
    })


@app.get("/health", response_model=APIResponse[dict])
async def health_check() -> APIResponse[dict]:
    """Health check endpoint for monitoring."""
    logger.debug("Health check endpoint accessed")
    return APIResponse.success_response({
        "status": "healthy",
        "version": settings.api_version,
        "service": "govcloud-ai-agent-poc"
    })


@app.get("/conversations")
async def redirect_conversations():
    """Redirect /conversations to /conversations/ for better UX."""
    logger.debug("Redirecting /conversations to /conversations/")
    return RedirectResponse(url="/conversations/", status_code=status.HTTP_301_MOVED_PERMANENTLY)