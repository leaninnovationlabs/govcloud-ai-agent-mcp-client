# GovCloud AI Agent PoC

A FastAPI-based AI agent system for GovCloud environments, featuring AWS Bedrock integration with Claude 3.5 Sonnet and Model Context Protocol (MCP) support for dynamic tool discovery and execution.

## Features

- **AI-Powered Conversations**: Claude 3.5 Sonnet integration via AWS Bedrock
- **Dynamic Tool Discovery**: MCP (Model Context Protocol) server integration with Wikipedia search
- **Modern Web Interface**: React frontend with real-time chat interface
- **Persistent Storage**: SQLite database for conversation history
- **Streaming Responses**: Real-time AI response streaming
- **FastAPI Backend**: Modern async Python web framework with comprehensive API
- **Environment-Based Configuration**: Secure configuration management

## Architecture

```
├── backend/                 # FastAPI backend application
│   ├── app/
│   │   ├── agent/          # AI agent logic and MCP integration
│   │   ├── conversation/   # Conversation management
│   │   ├── core/           # Configuration and utilities
│   │   ├── database/       # Database connection and models
│   │   └── util/           # Logging and middleware utilities
│   ├── docs/               # API documentation (Bruno collection)
│   └── alembic/           # Database migration scripts
├── frontend/               # React + Vite frontend application
│   ├── src/
│   │   ├── components/     # Reusable UI components
│   │   ├── pages/          # Page components (Chat)
│   │   └── lib/            # Utilities and state management
│   └── public/            # Static assets
├── mcp_server/            # MCP server implementation with Wikipedia integration
└── pyproject.toml         # uv project configuration
```

## Prerequisites

- **Python 3.12+** (managed by uv)
- **Node.js 18+** (for frontend development)
- **AWS Account** with Bedrock access
- **uv** package manager ([install instructions](https://docs.astral.sh/uv/getting-started/installation/))

## Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd govcloud-ai-agent-poc
   ```

2. **Install all dependencies**
   ```bash
   # Install Python dependencies with uv
   uv sync
   
   # Install frontend dependencies
   cd frontend
   npm install
   cd ..
   ```

3. **Set up environment variables**
   
   Create a `.env` file in the `backend/` directory:

   ```env
   # Database Configuration
   DATABASE_URL=sqlite+aiosqlite:///./chat.db

   # API Configuration
   API_TITLE=GovCloud AI Agent API
   API_VERSION=1.0.0

   # AWS Bedrock Configuration (uses AWS credential chain)
   AWS_REGION=us-east-1

   # Claude Model Configuration  
   CLAUDE_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0

   # MCP Server Configuration
   MCP_SERVER_URL=http://localhost:8001
   MCP_TIMEOUT=30.0

   # Application Configuration
   APP_NAME=GovCloud AI Agent
   DEBUG=false

   # Logging Configuration
   LOG_LEVEL=INFO
   LOG_MODE=LOCAL

   # Optional: Logfire token for observability
   LOGFIRE_TOKEN=
   ```

4. **Initialize the database**
   ```bash
   make migrate
   ```

## Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `DATABASE_URL` | Database connection string | `sqlite+aiosqlite:///./chat.db` | No |
| `API_TITLE` | API title for documentation | `GovCloud AI Agent API` | No |
| `API_VERSION` | API version | `1.0.0` | No |
| `AWS_REGION` | AWS region for Bedrock | `us-east-1` | No |
| `CLAUDE_MODEL_ID` | Claude model ID for Bedrock | `anthropic.claude-3-5-sonnet-20241022-v2:0` | No |
| `MCP_SERVER_URL` | MCP server endpoint URL | `http://localhost:8001` | No |
| `MCP_TIMEOUT` | MCP request timeout in seconds | `30.0` | No |
| `APP_NAME` | Application name | `GovCloud AI Agent` | No |
| `DEBUG` | Enable debug mode | `false` | No |
| `LOG_LEVEL` | Logging level | `INFO` | No |
| `LOG_MODE` | Logging format (`LOCAL` or `JSON`) | `LOCAL` | No |
| `LOGFIRE_TOKEN` | Logfire observability token | `` | No |

### AWS Bedrock Setup

**🔐 Security Approach**: This application uses the [AWS credential provider chain](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-quickstart.html) for secure authentication without hardcoded credentials.

1. **Enable Claude 3.5 Sonnet in Bedrock**
   - Navigate to AWS Bedrock console
   - Go to "Model access" in the left sidebar
   - Request access to "Anthropic Claude 3.5 Sonnet v2"
   - Wait for approval (usually immediate)

2. **Configure AWS Credentials**
   
   Choose the appropriate method for your environment:

   **For Local Development:**
   ```bash
   # AWS CLI (recommended)
   aws configure
   
   # AWS SSO (for organizations)
   aws configure sso
   
   # Named profiles
   aws configure --profile govcloud
   export AWS_PROFILE=govcloud
   ```

   **For Production:**
   - **EC2/ECS**: Use IAM roles
   - **Lambda**: Use execution roles
   - **CI/CD**: Use OIDC with IAM roles

3. **Verify Setup**
   ```bash
   # Test AWS access
   aws sts get-caller-identity
   aws bedrock list-foundation-models --region us-east-1
   
   # Comprehensive validation
   cd backend
   uv run python validate_aws_setup.py
   ```

## Running the Application

The project includes a comprehensive Makefile for easy development. Use `make help` to see all available commands.

### Quick Start

```bash
# Complete setup
make setup

# Start all services (backend + MCP server + frontend)
make run-all

# Access the application
# - Frontend: http://localhost:5173
# - Backend API: http://localhost:8000
# - MCP Server: http://localhost:8001
```

### Individual Services

```bash
# Backend only
make run-backend

# MCP server only  
make run-mcp

# Frontend only (in separate terminal)
cd frontend
npm run dev
```

### Development Commands

```bash
# Install dependencies
make install              # All dependencies
make install-backend      # Backend only
make install-mcp         # MCP server only

# Database operations
make migrate             # Apply migrations
make makemigrations m="description"  # Create new migration

# Docker operations
make docker-build        # Build backend container
make docker-run          # Run in container
make docker-stop         # Stop container

# Utilities
make clean              # Clean build artifacts
make status             # Show project status
```

## Frontend Development

The frontend is built with React, Vite, and TailwindCSS:

```bash
cd frontend

# Development server
npm run dev

# Build for production  
npm run build

# Preview production build
npm run preview

# Linting
npm run lint
```

### Frontend Features

- **Real-time Chat Interface**: Clean, modern chat UI
- **Conversation Management**: Create, switch, and manage multiple conversations
- **Streaming Responses**: Real-time AI response display
- **Responsive Design**: Works on desktop and mobile
- **State Management**: Zustand for efficient state handling

## API Usage

### Health Check
```bash
curl http://localhost:8000/health
```

### Create a Conversation
```bash
curl -X POST http://localhost:8000/conversations/ \
  -H "Content-Type: application/json" \
  -d '{"title": "My Chat Session"}'
```

### Send a Message
```bash
curl -X POST http://localhost:8000/conversations/{conversation_id}/messages \
  -H "Content-Type: application/json" \
  -d '{"content": "Hello, how can you help me?"}'
```

### Streaming Messages
```bash
curl -X POST http://localhost:8000/conversations/{conversation_id}/messages/stream \
  -H "Content-Type: application/json" \
  -d '{"content": "Tell me about AWS services"}' \
  --no-buffer
```

## API Documentation

Interactive API documentation is available at:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **Bruno Collection**: `backend/docs/` for manual testing

## MCP Server

The integrated MCP server provides Wikipedia search capabilities:

- **Search Wikipedia**: `search_wikipedia(query, limit=5)`
- **Get Article**: `get_wikipedia_article(title)`
- **Health Check**: `http://localhost:8001/health`

The MCP server automatically starts with `make run-all` and integrates with the AI agent for dynamic tool discovery.

## Database Management

### Migrations with uv

```bash
# Create a new migration
make makemigrations m="Description of changes"

# Apply migrations
make migrate

# Rollback (manual)
cd backend
uv run alembic downgrade -1
```

### Database Schema

- **Conversations**: Chat sessions with metadata
- **Messages**: Individual messages with role and content
- **Agent State**: Persistent agent context

## Logging

### Development Mode (`LOG_MODE=LOCAL`)
Colorized console output with structured information.

### Production Mode (`LOG_MODE=JSON`)
Structured JSON logs for aggregation systems.

### Observability
Optional Logfire integration for advanced monitoring and tracing.

## Troubleshooting

### Common Issues

1. **AWS Bedrock Access Denied**
   ```bash
   # Check credentials
   aws sts get-caller-identity
   
   # Verify Bedrock access
   aws bedrock list-foundation-models --region us-east-1
   
   # Run validation script
   cd backend && uv run python validate_aws_setup.py
   ```

2. **MCP Server Connection Issues**
   ```bash
   # Check if MCP server is running
   curl http://localhost:8001/health
   
   # Start MCP server
   make run-mcp
   ```

3. **Frontend Build Issues**
   ```bash
   cd frontend
   rm -rf node_modules package-lock.json
   npm install
   npm run dev
   ```

4. **Database Issues**
   ```bash
   # Reset database
   rm backend/chat.db
   make migrate
   ```

### Debug Mode

```bash
export DEBUG=true
export LOG_LEVEL=DEBUG
make run-backend
```

## Project Commands Reference

| Command | Description |
|---------|-------------|
| `make help` | Show all available commands |
| `make setup` | Complete project setup |
| `make install` | Install all dependencies |
| `make run-all` | Start all services |
| `make run-backend` | Start backend only |
| `make run-mcp` | Start MCP server only |
| `make migrate` | Apply database migrations |
| `make docker-build` | Build Docker image |
| `make clean` | Clean build artifacts |
| `make status` | Show project status |

## Security

- **AWS Credential Chain**: Secure credential management
- **No Hardcoded Secrets**: Environment-based configuration
- **HTTPS Required**: For production MCP server connections
- **CORS Configuration**: Frontend-backend communication
- **Structured Logging**: Security event tracking

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes with proper tests
4. Ensure code formatting: `make format` (when available)
5. Submit a pull request

## Support

For issues and questions:
- Create an issue in the repository
- Check the troubleshooting section
- Review AWS Bedrock documentation
- Consult MCP specification

---

**Note**: This is a Proof of Concept (PoC) application. Ensure proper security reviews and compliance checks before production deployment in GovCloud environments.
