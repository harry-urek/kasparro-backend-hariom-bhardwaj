# Kasparro Backend Service

A lightweight FastAPI-based backend service providing data retrieval and health monitoring endpoints.

## Table of Contents
- [Features](#features)
- [Project Structure](#project-structure)
- [Setup Instructions](#setup-instructions)
- [API Endpoints](#api-endpoints)
- [Design Explanation](#design-explanation)
- [Development](#development)
- [Docker Support](#docker-support)

## Features

- **FastAPI Framework**: Modern, fast, and production-ready Python web framework
- **Pagination Support**: Built-in pagination for data endpoints
- **Filtering Capability**: Flexible filtering options for data queries
- **Request Tracking**: Each request includes a unique `request_id` for tracing
- **Performance Monitoring**: API latency metrics returned with each response
- **Health Monitoring**: Database connectivity and ETL status checks
- **Docker Support**: Fully containerized with Docker and Docker Compose
- **Production Ready**: Includes Dockerfile, docker-compose, and Makefile for easy deployment

## Project Structure

```
kasparro-backend-hariom-bhardwaj/
├── app/
│   ├── __init__.py           # Application package initialization
│   └── main.py               # FastAPI application and endpoint definitions
├── Dockerfile                # Container image definition
├── docker-compose.yml        # Service orchestration
├── Makefile                  # Common commands and shortcuts
├── requirements.txt          # Python dependencies
├── .dockerignore            # Docker build exclusions
├── .gitignore               # Git exclusions
└── README.md                # This file
```

## Setup Instructions

### Prerequisites

- Python 3.11+
- Docker and Docker Compose (for containerized deployment)
- Make (optional, for using Makefile commands)

### Option 1: Local Development Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd kasparro-backend-hariom-bhardwaj
   ```

2. **Install dependencies**
   ```bash
   make install
   # OR
   pip install -r requirements.txt
   ```

3. **Run the application**
   ```bash
   make dev
   # OR
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

4. **Access the API**
   - API: http://localhost:8000
   - Interactive API Docs (Swagger): http://localhost:8000/docs
   - Alternative API Docs (ReDoc): http://localhost:8000/redoc

### Option 2: Docker Setup

1. **Build and start services**
   ```bash
   make build
   make up
   # OR
   docker-compose up -d --build
   ```

2. **View logs**
   ```bash
   make logs
   # OR
   docker-compose logs -f
   ```

3. **Stop services**
   ```bash
   make down
   # OR
   docker-compose down
   ```

## API Endpoints

### GET /data

Retrieves paginated data with optional filtering.

**Query Parameters:**
- `page` (int, default: 1): Page number (minimum: 1)
- `page_size` (int, default: 10): Items per page (range: 1-100)
- `filter_by` (string, optional): Filter criteria

**Response:**
```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "api_latency_ms": 12.34,
  "data": [],
  "page": 1,
  "page_size": 10,
  "total_items": 0
}
```

**Example:**
```bash
curl "http://localhost:8000/data?page=1&page_size=20&filter_by=active"
# OR
make data
```

### GET /health

Health check endpoint reporting service status.

**Response:**
```json
{
  "status": "healthy",
  "db_connected": true,
  "etl_last_run": "2025-12-22T10:30:00Z",
  "etl_status": "success"
}
```

**Example:**
```bash
curl http://localhost:8000/health
# OR
make health
```

### GET /

Root endpoint providing basic service information.

**Response:**
```json
{
  "message": "Kasparro Backend Service",
  "version": "1.0.0",
  "endpoints": ["/data", "/health"]
}
```

## Design Explanation

### Architecture Overview

The project follows a **lightweight microservice architecture** with these key design decisions:

#### 1. **FastAPI Framework**
- **Why FastAPI?**
  - High performance (comparable to NodeJS and Go)
  - Automatic API documentation (Swagger/OpenAPI)
  - Built-in data validation using Pydantic
  - Asynchronous support for scalability
  - Type hints and modern Python features

#### 2. **Endpoint Design**

##### `/data` Endpoint
- **Pagination**: Prevents memory issues and improves response times for large datasets
  - `page`: Allows navigation through result sets
  - `page_size`: Customizable results per page (capped at 100 for safety)
- **Filtering**: Flexible `filter_by` parameter for future query capabilities
- **Metadata**: Each response includes:
  - `request_id`: Unique UUID for request tracing and debugging
  - `api_latency_ms`: Performance monitoring in milliseconds

##### `/health` Endpoint
- **Service Monitoring**: Critical for production deployments
  - `db_connected`: Database connectivity status
  - `etl_last_run`: Timestamp of last ETL process
  - `etl_status`: Success/failure status of ETL operations
- **Status Reporting**: Overall service health ("healthy", "degraded", "unhealthy")

#### 3. **Response Models**
- Pydantic models ensure type safety and automatic validation
- Clear contract for API consumers
- Self-documenting through OpenAPI schema

#### 4. **Containerization**

##### Dockerfile
- **Base Image**: Python 3.11-slim for minimal footprint
- **Layer Optimization**: Requirements installed before code for better caching
- **Health Checks**: Built-in container health monitoring
- **Production Best Practices**:
  - Non-root user execution (can be added)
  - Minimal system dependencies
  - No cache directory pollution

##### Docker Compose
- **Service Orchestration**: Easy multi-container management
- **Networking**: Isolated bridge network for service communication
- **Volume Mounting**: Development-friendly hot-reload support
- **Future-Ready**: Commented database service template

#### 5. **Development Workflow**

##### Makefile
Provides convenient shortcuts for common operations:
- `make help`: Display all available commands
- `make dev`: Local development with hot-reload
- `make build`: Build Docker images
- `make up/down`: Start/stop services
- `make logs`: View application logs
- `make health/data`: Test endpoints quickly

### Scalability Considerations

1. **Horizontal Scaling**: Stateless design allows multiple instances
2. **Database Ready**: Architecture supports adding PostgreSQL/MySQL
3. **Caching Layer**: Easy to integrate Redis for performance
4. **Load Balancing**: Container-ready for orchestration (Kubernetes, Docker Swarm)
5. **Monitoring**: Request IDs and latency metrics enable observability

### Future Enhancements

The skeleton is designed to easily accommodate:
- Database integration (PostgreSQL, MongoDB, etc.)
- Authentication/Authorization (JWT, OAuth2)
- ETL pipeline integration
- Logging and monitoring (ELK stack, Prometheus)
- Rate limiting and caching
- Background task processing (Celery)
- API versioning
- Comprehensive testing suite

## Development

### Available Make Commands

Run `make help` to see all available commands:

```bash
make help              # Show help message
make install           # Install dependencies locally
make dev              # Run locally with hot-reload
make build            # Build Docker images
make up               # Start all services
make down             # Stop all services
make restart          # Restart all services
make logs             # View all logs
make logs-api         # View API logs only
make ps               # List running containers
make shell            # Open shell in API container
make clean            # Remove all containers and volumes
make health           # Test health endpoint
make data             # Test data endpoint
```

### Adding New Endpoints

1. Define Pydantic response models in `app/main.py`
2. Create endpoint function with appropriate decorators
3. Add input validation using Query/Path/Body parameters
4. Implement business logic (TODO sections)
5. Return structured response

### Adding Database Support

1. Uncomment database service in `docker-compose.yml`
2. Add database client library to `requirements.txt` (e.g., SQLAlchemy, asyncpg)
3. Create database connection module
4. Implement database queries in endpoint handlers
5. Update health check to verify database connectivity

## Docker Support

### Build and Run

```bash
# Build the image
docker build -t kasparro-backend .

# Run container
docker run -p 8000:8000 kasparro-backend

# With Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f api

# Stop services
docker-compose down
```

### Environment Variables

Configure the application using environment variables in `docker-compose.yml`:
- `ENV`: Environment name (development, staging, production)
- `LOG_LEVEL`: Logging level (debug, info, warning, error)

Add more as needed for database connections, API keys, etc.

## Testing

To be implemented:
```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run tests
make test
# OR
pytest tests/
```

## License

[Add your license here]

## Contributors

- Hariom Bhardwaj