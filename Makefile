# ==============================================================================
# Makefile for GovCloud AI Agent POC
# ==============================================================================

# Sensible defaults (based on https://tech.davis-hansson.com/p/make)
SHELL := bash
.ONESHELL:
.SHELLFLAGS := -eu -o pipefail -c
.DELETE_ON_ERROR:
MAKEFLAGS += --warn-undefined-variables
MAKEFLAGS += --no-builtin-rules

# Check for GNU Make 4.0+ (required for .RECIPEPREFIX)
ifeq ($(origin .RECIPEPREFIX), undefined)
  $(error This Make does not support .RECIPEPREFIX. Please use GNU Make 4.0 or later)
endif
.RECIPEPREFIX = >

# ==============================================================================
# Variables
# ==============================================================================

PROJECT_NAME := govcloud-ai-agent-poc
BACKEND_DIR := backend
MCP_SERVER_DIR := mcp_server
DOCKER_IMAGE := $(PROJECT_NAME)-backend
CONTAINER_NAME := backend-container
BACKEND_PORT := 8000
MCP_SERVER_PORT := 8001

# ==============================================================================
# Help System
# ==============================================================================

## Display this help message
help:
> @echo "$(PROJECT_NAME) - Available commands:"
> @echo ""
> @echo "Development Commands:"
> @echo "  install          Install all dependencies"
> @echo "  install-backend  Install backend dependencies only"
> @echo "  install-mcp      Install MCP server dependencies only"
> @echo "  run              Start the development server"
> @echo "  run-backend      Start backend development server"
> @echo "  run-mcp          Start MCP server"
> @echo "  run-all          Start both backend and MCP server in parallel"
> @echo ""
> @echo "Database Commands:"
> @echo "  migrate          Run database migrations"
> @echo "  makemigrations   Create new database migration (use: make makemigrations m='description')"
> @echo ""
> @echo "Docker Commands:"
> @echo "  docker-build     Build Docker image for backend"
> @echo "  docker-run       Run backend in Docker container"
> @echo "  docker-stop      Stop and remove Docker container"
> @echo "  docker-clean     Remove Docker image and container"
> @echo ""
> @echo "Testing & Quality:"
> @echo "  test             Run all tests"
> @echo "  lint             Run linting checks"
> @echo "  format           Format code"
> @echo ""
> @echo "Infrastructure Commands:"
> @echo "  infra-up         Deploy AWS data lake infrastructure"
> @echo "  infra-down       Destroy AWS data lake infrastructure"
> @echo "  infra-data       Generate and upload sample data to S3"
> @echo ""
> @echo "Utility Commands:"
> @echo "  clean            Clean build artifacts and cache files"
> @echo "  setup            Complete project setup (install + migrate)"
> @echo "  status           Show project status"
> @echo "  help             Show this help message"
> @echo ""
> @echo "Example usage:"
> @echo "  make setup                    # Complete setup"
> @echo "  make run-all                  # Start both servers"
> @echo "  make makemigrations m='Add user model'  # Create migration"

.PHONY: help

# Default target
.DEFAULT_GOAL := help

# ==============================================================================
# Setup & Installation
# ==============================================================================

## Complete project setup (install dependencies and run migrations)
setup: install migrate
> @echo "✅ Project setup complete!"

## Install all dependencies
install:
> @echo "📦 Installing all dependencies..."
> uv sync --extra backend --extra mcp
> @echo "✅ All dependencies installed!"

## Install backend dependencies
install-backend:
> @echo "📦 Installing backend dependencies..."
> uv sync --extra backend
> @echo "✅ Backend dependencies installed!"

## Install MCP server dependencies
install-mcp:
> @echo "📦 Installing MCP server dependencies..."
> uv sync --extra mcp
> @echo "✅ MCP server dependencies installed!"

.PHONY: setup install install-backend install-mcp

# ==============================================================================
# Development
# ==============================================================================

## Start the development server (alias for run-backend)
run: run-backend

## Start backend development server
run-backend:
> @echo "🚀 Starting backend development server..."
> cd $(BACKEND_DIR) && uv run uvicorn app.app:app --reload --host 0.0.0.0 --port $(BACKEND_PORT)

## Start MCP server
run-mcp:
> @echo "🚀 Starting MCP server..."
> uv run --extra mcp python -m $(MCP_SERVER_DIR).main

## Start both backend and MCP server in parallel
run-all:
> @echo "🚀 Starting both backend and MCP server..."
> @echo "Backend will run on http://localhost:$(BACKEND_PORT)"
> @echo "MCP server will run on http://localhost:$(MCP_SERVER_PORT)"
> @echo "Use Ctrl+C to stop both servers"
> @echo ""
> @trap 'echo "Stopping servers..."; kill 0' INT; \
> (cd $(BACKEND_DIR) && uv run uvicorn app.app:app --reload --host 0.0.0.0 --port $(BACKEND_PORT)) & \
> (uv run --extra mcp python -m $(MCP_SERVER_DIR).main) & \
> wait

.PHONY: run run-backend run-mcp run-all

# ==============================================================================
# Database Operations
# ==============================================================================

## Run database migrations
migrate: migrate-backend

## Run backend database migrations
migrate-backend:
> @echo "🗄️  Running database migrations..."
> cd $(BACKEND_DIR) && uv run alembic upgrade head
> @echo "✅ Database migrations complete!"

## Create new database migration (use: make makemigrations m='description')
makemigrations: makemigrations-backend

## Create new backend database migration
makemigrations-backend:
> @if [ -z "$(m)" ]; then \
>   echo "❌ Error: Migration message required. Use: make makemigrations m='description'"; \
>   exit 1; \
> fi
> @echo "📝 Creating new migration: $(m)"
> cd $(BACKEND_DIR) && uv run alembic revision --autogenerate -m "$(m)"
> @echo "✅ Migration created!"

.PHONY: migrate migrate-backend makemigrations makemigrations-backend

# ==============================================================================
# Docker Operations
# ==============================================================================

## Build Docker image for backend
docker-build:
> @echo "🐳 Building Docker image: $(DOCKER_IMAGE)"
> docker build -t $(DOCKER_IMAGE) -f $(BACKEND_DIR)/Dockerfile .
> @echo "✅ Docker image built successfully!"

## Run backend in Docker container
docker-run: docker-build
> @echo "🚀 Running backend in Docker container..."
> @if docker ps -a --format 'table {{.Names}}' | grep -q "$(CONTAINER_NAME)"; then \
>   echo "🛑 Stopping existing container..."; \
>   docker stop $(CONTAINER_NAME) 2>/dev/null || true; \
>   docker rm $(CONTAINER_NAME) 2>/dev/null || true; \
> fi
> docker run -d -p $(BACKEND_PORT):$(BACKEND_PORT) --name $(CONTAINER_NAME) $(DOCKER_IMAGE)
> @echo "✅ Backend running at http://localhost:$(BACKEND_PORT)"

## Stop and remove Docker container
docker-stop:
> @echo "🛑 Stopping Docker container..."
> @if docker ps --format 'table {{.Names}}' | grep -q "$(CONTAINER_NAME)"; then \
>   docker stop $(CONTAINER_NAME); \
>   echo "✅ Container stopped!"; \
> else \
>   echo "ℹ️  Container not running"; \
> fi
> @if docker ps -a --format 'table {{.Names}}' | grep -q "$(CONTAINER_NAME)"; then \
>   docker rm $(CONTAINER_NAME); \
>   echo "✅ Container removed!"; \
> fi

## Remove Docker image and container
docker-clean: docker-stop
> @echo "🧹 Cleaning Docker resources..."
> @if docker images --format 'table {{.Repository}}' | grep -q "$(DOCKER_IMAGE)"; then \
>   docker rmi $(DOCKER_IMAGE); \
>   echo "✅ Docker image removed!"; \
> else \
>   echo "ℹ️  Docker image not found"; \
> fi

.PHONY: docker-build docker-run docker-stop docker-clean

# ==============================================================================
# Testing & Quality Assurance
# ==============================================================================

## Run all tests
test:
> @echo "🧪 Running tests..."
> @if [ -f "$(BACKEND_DIR)/pyproject.toml" ]; then \
>   cd $(BACKEND_DIR) && uv run pytest -v; \
> else \
>   echo "⚠️  No tests configured yet"; \
> fi

## Run linting checks
lint:
> @echo "🔍 Running linting checks..."
> @if [ -f "$(BACKEND_DIR)/pyproject.toml" ]; then \
>   cd $(BACKEND_DIR) && uv run ruff check .; \
> else \
>   echo "⚠️  Linting not configured yet"; \
> fi

## Format code
format:
> @echo "🎨 Formatting code..."
> @if [ -f "$(BACKEND_DIR)/pyproject.toml" ]; then \
>   cd $(BACKEND_DIR) && uv run ruff format .; \
> else \
>   echo "⚠️  Code formatting not configured yet"; \
> fi

.PHONY: test lint format

# ==============================================================================
# Utility Commands
# ==============================================================================

## Clean build artifacts and cache files
clean:
> @echo "🧹 Cleaning build artifacts..."
> find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
> find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
> find . -type f -name "*.pyc" -delete 2>/dev/null || true
> find . -type f -name "*.pyo" -delete 2>/dev/null || true
> find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
> find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
> @echo "✅ Cleanup complete!"

## Show project status
status:
> @echo "📊 Project Status:"
> @echo "=================="
> @echo "Project: $(PROJECT_NAME)"
> @echo "Backend Directory: $(BACKEND_DIR)"
> @echo "Backend Port: $(BACKEND_PORT)"
> @echo "MCP Server Directory: $(MCP_SERVER_DIR)"
> @echo "MCP Server Port: $(MCP_SERVER_PORT)"
> @echo ""
> @echo "Docker Status:"
> @if docker ps --format 'table {{.Names}}\t{{.Status}}' | grep -q "$(CONTAINER_NAME)"; then \
>   echo "  Container: Running"; \
>   docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | grep "$(CONTAINER_NAME)"; \
> else \
>   echo "  Container: Not running"; \
> fi
> @if docker images --format 'table {{.Repository}}\t{{.Tag}}\t{{.Size}}' | grep -q "$(DOCKER_IMAGE)"; then \
>   echo "  Image: Available"; \
>   docker images --format 'table {{.Repository}}\t{{.Tag}}\t{{.Size}}' | grep "$(DOCKER_IMAGE)"; \
> else \
>   echo "  Image: Not built"; \
> fi
> @echo ""
> @echo "Dependencies:"
> @if [ -f "uv.lock" ]; then \
>   echo "  ✅ uv.lock found"; \
> else \
>   echo "  ❌ uv.lock missing - run 'make install'"; \
> fi
> @echo ""
> @echo "Server Endpoints:"
> @echo "  Backend API: http://localhost:$(BACKEND_PORT)"
> @echo "  MCP Server: http://localhost:$(MCP_SERVER_PORT)/mcp"
> @echo "  MCP Health: http://localhost:$(MCP_SERVER_PORT)/health"

.PHONY: clean status

# ==============================================================================
# Infrastructure Management
# ==============================================================================

INFRA_DIR := infra
INFRA_ENV ?= dev

## Deploy AWS data lake infrastructure
infra-up:
> @echo "🚀 Deploying maritime data lake infrastructure..."
> @echo "   Environment: $(INFRA_ENV)"
> cd $(INFRA_DIR) && terraform init
> cd $(INFRA_DIR) && terraform plan -var="environment=$(INFRA_ENV)"
> cd $(INFRA_DIR) && terraform apply -var="environment=$(INFRA_ENV)" -auto-approve
> @echo "✅ Infrastructure deployment complete!"
> @echo ""
> @echo "🔗 Next steps:"
> @echo "  1. Run 'make infra-data' to generate and upload sample data"
> @echo "  2. Check AWS Athena console to query your data lake"

## Destroy AWS data lake infrastructure
infra-down:
> @echo "💥 Destroying maritime data lake infrastructure..."
> @echo "   Environment: $(INFRA_ENV)"
> @echo "⚠️  This will permanently delete all infrastructure and data!"
> @read -p "Are you sure? Type 'yes' to continue: " confirm && [ "$$confirm" = "yes" ]
> cd $(INFRA_DIR) && terraform destroy -var="environment=$(INFRA_ENV)" -auto-approve
> @echo "✅ Infrastructure destroyed!"

## Generate and upload sample data to S3
infra-data:
> @echo "📊 Generating and uploading maritime shipping data..."
> @echo "🔧 Installing Python dependencies..."
> cd $(INFRA_DIR) && pip install -r requirements.txt
> @echo "🚢 Generating sample data..."
> cd $(INFRA_DIR)/scripts && python generate_sample_data.py
> @echo "📤 Uploading data and running Glue crawler..."
> cd $(INFRA_DIR)/scripts && python upload_data_and_crawl.py
> @echo "✅ Data lake is ready for querying in Athena!"

## Show infrastructure status
infra-status:
> @echo "📋 Infrastructure Status:"
> @echo "   Environment: $(INFRA_ENV)"
> @if [ -f "$(INFRA_DIR)/.terraform/terraform.tfstate" ] || [ -f "$(INFRA_DIR)/terraform.tfstate" ]; then \
>   echo "   ✅ Terraform state found"; \
>   cd $(INFRA_DIR) && terraform show -json | jq -r '.values.outputs | to_entries[] | "   \(.key): \(.value.value)"' 2>/dev/null || echo "   ℹ️  Use 'terraform output' for detailed info"; \
> else \
>   echo "   ❌ No Terraform state found - run 'make infra-up' first"; \
> fi

## Initialize Terraform only
infra-init:
> @echo "🔧 Initializing Terraform..."
> cd $(INFRA_DIR) && terraform init
> @echo "✅ Terraform initialized!"

## Plan infrastructure changes
infra-plan:
> @echo "📋 Planning infrastructure changes..."
> @echo "   Environment: $(INFRA_ENV)"
> cd $(INFRA_DIR) && terraform plan -var="environment=$(INFRA_ENV)"

.PHONY: infra-up infra-down infra-data infra-status infra-init infra-plan

# ==============================================================================
# Legacy aliases for backward compatibility
# ==============================================================================

docker-build-backend: docker-build
docker-run-backend: docker-run

.PHONY: docker-build-backend docker-run-backend
