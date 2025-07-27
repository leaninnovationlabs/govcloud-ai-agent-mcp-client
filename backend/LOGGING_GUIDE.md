# Structured Logging Guide

## Overview

This guide covers the comprehensive structured logging implementation for the GovCloud AI Agent POC. The logging system follows best practices from the Effective Python book and [structured logging principles](https://stevetarver.github.io/2017/05/10/python-falcon-logging.html), providing both human-readable development logs and machine-parseable production logs.

## Features

### ✨ **Key Capabilities**
- **Structured JSON logging** for production environments
- **Human-readable colorized logs** for development
- **Request ID tracking** across all operations
- **Performance timing** with automatic operation duration tracking
- **Sensitive data sanitization** (passwords, tokens, etc.)
- **Exception handling** with full stack traces
- **Service identification** metadata in every log entry
- **Thread-safe** request context management

### 🏗️ **Architecture**
- **LoggerMixin**: Provides logging capabilities to any class
- **LogProcessor**: Custom processors for structured data
- **LoggingMiddleware**: Request/response logging with timing
- **Configuration**: Environment-based log level and format control

## Configuration

### Environment Variables

```bash
# Set log level (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL=INFO

# Set log format (LOCAL for development, JSON for production)
LOG_MODE=LOCAL
```

### Development vs Production

**Development (LOG_MODE=LOCAL)**:
```
2025-07-26 18:58:07.524570 [info] FastAPI application initialized [app.app] 
service_name=govcloud-ai-agent-poc service_type=api service_version=1.0.0 
thread_id=MainThread title='GovCloud AI Agent API' version=1.0.0
```

**Production (LOG_MODE=JSON)**:
```json
{
  "timestamp": "2025-07-26T18:58:07.524570Z",
  "level": "info", 
  "logger": "app.app",
  "message": "FastAPI application initialized",
  "service_name": "govcloud-ai-agent-poc",
  "service_type": "api",
  "service_version": "1.0.0",
  "thread_id": "MainThread",
  "title": "GovCloud AI Agent API",
  "version": "1.0.0"
}
```

## Usage Examples

### 1. Basic Logging with LoggerMixin

```python
from app.util.logging import LoggerMixin

class MyService(LoggerMixin):
    def __init__(self):
        super().__init__()
        self._log_info("Service initialized")
    
    def process_data(self, data_id: int):
        self._log_info("Processing data", data_id=data_id, size=len(data))
        
        try:
            # Processing logic here
            result = self._do_processing(data_id)
            self._log_info("Data processed successfully", 
                          data_id=data_id, 
                          result_count=len(result))
            return result
        except Exception as e:
            self._log_error("Failed to process data", 
                           exc_info=e, 
                           data_id=data_id)
            raise
```

### 2. Operation Timing with Context Manager

```python
class ConversationService(LoggerMixin):
    async def create_conversation(self):
        with self._log_operation("create_new_conversation"):
            self._log_info("Creating new conversation")
            
            # Business logic here
            conversation = await self.repository.create_conversation()
            
            self._log_info("Conversation created successfully",
                          conversation_id=conversation.id)
            return conversation
```

**Output**:
```
[info] Operation started: create_new_conversation
[info] Creating new conversation
[info] Conversation created successfully conversation_id=123
[info] Operation completed: create_new_conversation operation_duration_ms=45.23
```

### 3. Request ID Tracking

```python
from app.util.logging import set_request_id, get_request_id

# In middleware or request handler
request_id = set_request_id("custom-request-id")

# Anywhere in the request lifecycle
current_request_id = get_request_id()  # Returns "custom-request-id"

# All logs will automatically include this request_id
self._log_info("Processing request")  # Includes request_id=custom-request-id
```

### 4. Manual Logger Usage

```python
from app.util.logging import get_logger

logger = get_logger(__name__)

logger.info("Manual log entry", 
           custom_field="value",
           count=42)
```

### 5. Performance Monitoring

```python
class MessageRepository(LoggerMixin):
    async def create_message(self, content: str, role: MessageRole, conversation_id: int):
        with self._log_operation("db_create_message", 
                                role=role.value, 
                                conversation_id=conversation_id):
            
            self._log_info("Creating message in database",
                          content_length=len(content),
                          role=role.value)
            
            # Database operation
            message = Message(content=content, role=role.value, conversation_id=conversation_id)
            await self.session.commit()
            
            self._log_info("Message created successfully",
                          message_id=message.id,
                          timestamp=message.timestamp.isoformat())
            
            return message
```

## Log Levels and When to Use Them

### 📢 **INFO Level** (Default for Services/Repositories)
Use for important business events and milestones:
```python
self._log_info("User authenticated successfully", user_id=123)
self._log_info("Payment processed", amount=99.99, transaction_id="tx_123")
self._log_info("Email sent", recipient="user@example.com", template="welcome")
```

### 🐛 **DEBUG Level**
Use for detailed tracing and troubleshooting:
```python
self._log_debug("Cache miss, fetching from database", key="user:123")
self._log_debug("SQL query executed", query="SELECT * FROM users WHERE id = ?", params=[123])
self._log_debug("Validation passed", field="email", value="user@example.com")
```

### ⚠️ **WARNING Level**
Use for recoverable issues that need attention:
```python
self._log_warning("Rate limit approaching", current_requests=450, limit=500)
self._log_warning("Fallback to default value", requested="custom", fallback="default")
self._log_warning("Deprecated API used", endpoint="/v1/old", user_id=123)
```

### ❌ **ERROR Level**
Use for exceptions and critical failures:
```python
self._log_error("Database connection failed", exc_info=e, retry_count=3)
self._log_error("Payment processing failed", exc_info=e, order_id=123, amount=99.99)
```

## Request/Response Logging

The `LoggingMiddleware` automatically logs all HTTP requests and responses:

### Request Logging
```python
# Automatic log entry for each request
{
  "message": "HTTP request received",
  "event_type": "http_request",
  "request_id": "uuid-here",
  "method": "POST",
  "path": "/v1/chat/",
  "client_ip": "192.168.1.100", 
  "user_agent": "curl/7.68.0",
  "request_body": {
    "content": "Hello AI",
    "conversation_id": 1
  }
}
```

### Response Logging
```python
{
  "message": "HTTP request completed",
  "event_type": "http_response", 
  "request_id": "uuid-here",
  "method": "POST",
  "path": "/v1/chat/",
  "status_code": 200,
  "duration_ms": 1250.45
}
```

## Security & Privacy

### Automatic Sensitive Data Sanitization

The logging system automatically redacts sensitive fields:

```python
# Input
request_body = {
    "username": "john_doe",
    "password": "secret123",
    "api_key": "sk-1234567890",
    "content": "Hello world"
}

# Logged as  
request_body = {
    "username": "john_doe", 
    "password": "***REDACTED***",
    "api_key": "***REDACTED***",
    "content": "Hello world"
}
```

Sensitive keywords automatically redacted:
- `password`, `token`, `secret`, `key`, `auth`, `credential`, `api_key`

## Best Practices

### ✅ **Do's**
1. **Use structured data**: Include relevant fields as keyword arguments
   ```python
   self._log_info("User login", user_id=123, ip_address="192.168.1.1", success=True)
   ```

2. **Log business events**: Capture important state changes and milestones
   ```python
   self._log_info("Order completed", order_id=456, total_amount=99.99, items_count=3)
   ```

3. **Include context**: Add relevant IDs and metadata
   ```python
   self._log_info("Processing chat message", conversation_id=1, message_length=150)
   ```

4. **Use operation timing**: Wrap expensive operations
   ```python
   with self._log_operation("expensive_calculation", dataset_size=1000):
       result = expensive_function()
   ```

### ❌ **Don'ts**
1. **Don't log sensitive data** directly (auto-sanitization helps but be careful)
   ```python
   # BAD
   self._log_info("User data", raw_password=password)
   
   # GOOD  
   self._log_info("User authentication", user_id=user.id, success=True)
   ```

2. **Don't over-log** in tight loops
   ```python
   # BAD
   for item in items:
       self._log_debug("Processing item", item_id=item.id)  # Too noisy
   
   # GOOD
   self._log_info("Processing batch", batch_size=len(items))
   for i, item in enumerate(items):
       if i % 100 == 0:  # Log every 100 items
           self._log_debug("Batch progress", processed=i, total=len(items))
   ```

3. **Don't use f-strings for log messages** (loses structured data benefits)
   ```python
   # BAD
   self._log_info(f"User {user_id} logged in")
   
   # GOOD
   self._log_info("User logged in", user_id=user_id)
   ```

## Monitoring & Observability

### Log Aggregation
In production with `LOG_MODE=JSON`, logs can be ingested by:
- **ELK Stack** (Elasticsearch, Logstash, Kibana)
- **Grafana Loki**
- **AWS CloudWatch**
- **Google Cloud Logging**
- **Azure Monitor**

### Key Metrics to Monitor
1. **Error rates** by endpoint and error type
2. **Response times** using `duration_ms` field
3. **Request volumes** by path and method
4. **Business metrics** from custom log fields

### Alerting Examples
```javascript
// High error rate alert
count(level="error" AND service_name="govcloud-ai-agent-poc") > 10 in 5 minutes

// Slow response alert  
p95(duration_ms WHERE event_type="http_response") > 2000ms

// Business metric alert
count(operation="process_chat_message" AND error_type IS NOT NULL) > 5 in 10 minutes
```

## Troubleshooting

### Common Issues

1. **Missing request IDs**: Ensure `LoggingMiddleware` is registered in app
2. **No structured fields**: Use keyword arguments, not f-strings
3. **Sensitive data leaking**: Check sanitization keywords are comprehensive
4. **Performance impact**: Use appropriate log levels (avoid DEBUG in production)

### Debug Configuration

```python
# Enable debug logging for specific modules
import logging
logging.getLogger("app.agent.service").setLevel(logging.DEBUG)

# Test logging configuration
from app.util.logging import get_logger
logger = get_logger("test")
logger.info("Test message", test_field="value")
```

## Examples in Codebase

See the implemented logging in:
- `app/conversation/service.py` - Service-level business logic logging
- `app/conversation/repository.py` - Database operation logging  
- `app/agent/service.py` - AI agent processing with streaming metrics
- `app/agent/repository.py` - Message storage with performance tracking
- `app/util/middleware.py` - Request/response logging with timing

This logging system provides comprehensive observability while maintaining excellent developer experience and production security. 