# GovCloud AI Agent PoC

A FastAPI-based AI agent system for GovCloud environments, featuring AWS Bedrock integration with Claude 3.5 Sonnet and Model Context Protocol (MCP) support for dynamic tool discovery and execution.

## Features

- **AI-Powered Conversations**: Claude 3.5 Sonnet integration via AWS Bedrock
- **Dynamic Tool Discovery**: MCP (Model Context Protocol) server integration
- **Persistent Storage**: SQLite database for conversation history
- **Streaming Responses**: Real-time AI response streaming
- **FastAPI Backend**: Modern async Python web framework
- **Environment-Based Configuration**: Secure configuration management

## Architecture

```
├── backend/                 # FastAPI backend application
│   ├── app/
│   │   ├── agent/          # AI agent logic and MCP integration
│   │   ├── conversation/   # Conversation management
│   │   ├── core/           # Configuration and utilities
│   │   └── database/       # Database connection and models
│   ├── docs/               # API documentation (Bruno collection)
│   └── alembic/           # Database migration scripts
├── frontend/               # Frontend application (if applicable)
├── mcp_server/            # MCP server implementation
└── main.py                # Application entry point
```

## Prerequisites

- Python 3.8+
- AWS Account with Bedrock access
- MCP Server endpoint
- SQLite (included)

## Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd govcloud-ai-agent-poc
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   # or if using uv
   uv sync
   ```

3. **Set up environment variables**
   
   Create a `.env` file in the `backend/` directory with the following configuration:

   ```env
   # Database Configuration
   DATABASE_URL=sqlite+aiosqlite:///./chat.db

   # API Configuration
   API_TITLE=GovCloud AI Agent API
   API_VERSION=1.0.0

   # AWS Bedrock Configuration (uses AWS credential chain - see setup below)
   AWS_REGION=us-east-1

   # Claude Model Configuration  
   CLAUDE_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0

   # MCP Server Configuration
   MCP_SERVER_URL=https://your-mcp-server.example.com
   MCP_TIMEOUT=30.0

   # Application Configuration
   APP_NAME=GovCloud AI Agent
   DEBUG=false

   # Logging Configuration
   LOG_LEVEL=INFO
   LOG_MODE=LOCAL
   ```

4. **Initialize the database**
   ```bash
   cd backend
   alembic upgrade head
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
| `MCP_SERVER_URL` | MCP server endpoint URL | - | Yes |
| `MCP_TIMEOUT` | MCP request timeout in seconds | `30.0` | No |
| `APP_NAME` | Application name | `GovCloud AI Agent` | No |
| `DEBUG` | Enable debug mode | `false` | No |
| `LOG_LEVEL` | Logging level | `INFO` | No |
| `LOG_MODE` | Logging format (`LOCAL` or `JSON`) | `LOCAL` | No |

### AWS Bedrock Setup

**🔐 2025 Security Approach**: This application follows modern AWS security best practices by using the [AWS credential provider chain](https://www.linkedin.com/pulse/cracking-aws-credential-chain-what-you-need-know-never-konkowski-0ofwe) instead of hardcoded credentials. This means:
- ✅ Automatic credential discovery
- ✅ No secrets in code or environment variables  
- ✅ Works seamlessly across local dev, CI/CD, and production
- ✅ Follows AWS Well-Architected Security Pillar

1. **Enable Claude 3.5 Sonnet in Bedrock**
   - Navigate to AWS Bedrock console
   - Go to "Model access" in the left sidebar
   - Request access to "Anthropic Claude 3.5 Sonnet v2"
   - Wait for approval (usually immediate for most regions)

2. **Configure AWS Credentials (2025 Best Practices)**
   
   The application automatically uses the [AWS credential provider chain](https://www.linkedin.com/pulse/cracking-aws-credential-chain-what-you-need-know-never-konkowski-0ofwe). Choose the appropriate method for your environment:

   **For Local Development:**
   ```bash
   # Option A: AWS CLI profiles (recommended)
   aws configure
   # Follow prompts to set up credentials and default region
   
   # Option B: AWS SSO (for organizations using AWS Identity Center)
   aws configure sso
   # Follow prompts to set up SSO profile
   
   # Option C: Named profiles for multiple accounts
   aws configure --profile dev
   aws configure --profile prod
   export AWS_PROFILE=dev  # Use specific profile
   ```

   **For Production Deployments:**
   - **EC2/ECS**: Use IAM roles (no credential configuration needed)
   - **Lambda**: Use execution roles (automatic)
   - **GitHub Actions**: Use OIDC with IAM roles
   - **Docker**: Mount `~/.aws` or use IAM roles

   **⚠️ Security Note**: Never use `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` environment variables in 2025. This is considered a security anti-pattern.

3. **Verify Bedrock Access**
   ```bash
   aws bedrock list-foundation-models --region us-east-1
   ```

4. **Test Your Setup**
   ```bash
   # Quick AWS CLI test
   aws sts get-caller-identity
   aws bedrock list-foundation-models --region us-east-1
   
   # Comprehensive validation (recommended)
   cd backend
   uv run python validate_aws_setup.py
   ```
   
   The validation script will check:
   - ✅ AWS credential chain configuration
   - ✅ Bedrock service access
   - ✅ Claude 3.5 Sonnet model availability
   - ✅ IAM permissions

### MCP Server Configuration

The application connects to an MCP (Model Context Protocol) server for dynamic tool discovery. Ensure your MCP server:

- Implements the MCP specification
- Is accessible via HTTPS
- Supports the tools/list and tools/call endpoints
- Has proper authentication if required

## Running the Application

### Development Mode

```bash
# From project root
python main.py

# Or using uvicorn directly
cd backend
uvicorn app.app:app --reload --host 0.0.0.0 --port 8000
```

### Production Mode

```bash
# Set production environment variables
export DEBUG=false
export LOG_MODE=JSON
export LOG_LEVEL=WARNING

# Run with production ASGI server
uvicorn backend.app.app:app --host 0.0.0.0 --port 8000 --workers 4
```

### Using Docker

```bash
cd backend
docker build -t govcloud-ai-agent .
docker run -p 8000:8000 --env-file .env govcloud-ai-agent
```

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
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

Bruno API collection is available in `backend/docs/` for testing.

## Database Management

### Migrations

```bash
cd backend

# Create a new migration
alembic revision --autogenerate -m "Description of changes"

# Apply migrations
alembic upgrade head

# Rollback migrations
alembic downgrade -1
```

### Database Schema

The application uses SQLAlchemy with async support. Main entities:
- **Conversations**: Chat sessions with metadata
- **Messages**: Individual messages in conversations
- **Agent State**: Persistent agent state and context

## Logging

The application supports two logging modes:

### Local Development (`LOG_MODE=LOCAL`)
Human-readable console output with colors and formatting.

### Production (`LOG_MODE=JSON`)
Structured JSON logs suitable for log aggregation systems.

### Log Levels
- `DEBUG`: Detailed diagnostic information
- `INFO`: General application flow
- `WARNING`: Important events that aren't errors
- `ERROR`: Error conditions
- `CRITICAL`: Critical errors that may abort

## Troubleshooting

### Common Issues

1. **AWS Bedrock Access Denied**
   - Check your AWS credential chain: `aws sts get-caller-identity`
   - Verify Claude 3.5 Sonnet access is enabled in Bedrock console
   - Ensure your IAM user/role has `bedrock:InvokeModel` permissions
   - Test with: `aws bedrock list-foundation-models --region us-east-1`

2. **MCP Server Connection Issues**
   - Verify the MCP server URL is accessible
   - Check network connectivity and firewall rules
   - Validate MCP server implementation

3. **Database Connection Issues**
   - Check database file permissions
   - Verify SQLite installation
   - Run database migrations

4. **Configuration Issues**
   - Ensure `.env` file is in the `backend/` directory
   - Check for typos in variable names
   - Verify file encoding (UTF-8)
   - For AWS issues, check credential chain: `aws configure list`

### Debug Mode

Enable debug mode for detailed logging:
```bash
export DEBUG=true
export LOG_LEVEL=DEBUG
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## Security

- **Never commit AWS credentials to version control**
- **Use AWS credential chain** (IAM roles, AWS CLI profiles, AWS SSO) - never use hardcoded credentials
- **Avoid `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` environment variables** in 2025
- **Ensure MCP server connections use HTTPS**
- **Regular dependency updates** and security scanning
- **Follow AWS Well-Architected Security Pillar** best practices
- **Use least privilege IAM policies** for all resources
- **Enable CloudTrail logging** for audit trails

## Support

For issues and questions:
- Create an issue in the repository
- Check the troubleshooting section
- Review AWS Bedrock documentation
- Consult MCP specification

---

**Note**: This is a Proof of Concept (PoC) application. Ensure proper security reviews and compliance checks before production deployment in GovCloud environments.
