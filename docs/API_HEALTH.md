# Health Check API Documentation

## Overview

The HR AI Platform provides multiple health check endpoints for different monitoring purposes. These endpoints are used by:

- **Load Balancers**: To route traffic only to healthy instances
- **Orchestrators** (Kubernetes, Docker Swarm): To manage container lifecycle
- **Monitoring Systems**: To track system health and uptime
- **CI/CD Pipelines**: To verify deployment success

---

## Health Check Endpoints

### 1. Basic Health Check

**Endpoint**: `GET /health`

**Purpose**: Liveness probe - confirms the application is running

**Use Case**: 
- Kubernetes liveness probe
- Load balancer health check
- Basic uptime monitoring

**Response**:
```json
{
  "status": "up",
  "timestamp": "2026-03-16T12:00:00.000Z",
  "version": "1.0.0",
  "environment": "production"
}
```

**Response Codes**:
| Code | Description |
|------|-------------|
| 200 | Application is running |

---

### 2. Readiness Check

**Endpoint**: `GET /readiness`

**Purpose**: Readiness probe - confirms the application can handle requests

**Use Case**:
- Kubernetes readiness probe
- Load balancer registration
- Pre-traffic validation

**Response**:
```json
{
  "status": "ready",
  "components": {
    "database": "connected"
  }
}
```

**Response Codes**:
| Code | Description |
|------|-------------|
| 200 | Ready to handle requests |
| 503 | Not ready (database connection failed) |

**Validation**:
- Tests database connectivity with `SELECT 1`
- If database is unreachable, returns 503

---

### 3. Liveness Check

**Endpoint**: `GET /liveness`

**Purpose**: Alias for `/health` - used by Kubernetes

**Response**:
```json
{
  "status": "up",
  "timestamp": "2026-03-16T12:00:00.000Z",
  "version": "1.0.0",
  "environment": "production"
}
```

---

### 4. System Status

**Endpoint**: `GET /system/status`

**Purpose**: Comprehensive system health for DevOps monitoring

**Use Case**:
- Dashboard monitoring
- Incident investigation
- System overview for operators

**Response**:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "build_id": "abc123",
  "commit_hash": "def456",
  "environment": "production",
  "timestamp": "2026-03-16T12:00:00.000Z",
  "components": {
    "database": {
      "status": "connected",
      "version": "PostgreSQL 15.4 on x86_64-pc-linux-gnu"
    },
    "ai_service": {
      "status": "configured",
      "model": "google/gemini-2.0-flash-001",
      "kill_switch": false
    },
    "security": {
      "rate_limiting": "enabled",
      "csrf_protection": "enabled",
      "cors_origins_count": 3
    }
  }
}
```

**Component Status Values**:

| Component | Possible Status |
|-----------|-----------------|
| database | `connected`, `disconnected` |
| ai_service | `configured`, `not_configured`, `error` |
| security | `enabled`, `disabled_dev` |

**Overall Status Values**:
| Status | Meaning |
|--------|---------|
| `healthy` | All components working |
| `degraded` | Some components failed |

---

### 5. Metrics Endpoint

**Endpoint**: `GET /metrics`

**Purpose**: Prometheus-compatible metrics for monitoring systems

**Use Case**:
- Prometheus scraping
- Grafana dashboards
- Performance monitoring

**Response**: Prometheus format
```
# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total{method="GET",endpoint="/api/employees",status="200",domain="employees"} 142

# HELP http_request_duration_seconds HTTP request latency
# TYPE http_request_duration_seconds histogram
http_request_duration_seconds_bucket{endpoint="/api/employees",domain="employees",le="0.1"} 89
```

**Available Metrics**:
| Metric | Type | Description |
|--------|------|-------------|
| `http_requests_total` | Counter | Total requests by endpoint, method, status |
| `http_request_duration_seconds` | Histogram | Request latency |
| `ai_failures_total` | Counter | AI service failures |
| `active_background_tasks` | Gauge | Active background tasks |

---

## Kubernetes Deployment Example

```yaml
apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      containers:
        - name: hr-backend
          ports:
            - containerPort: 8000
          livenessProbe:
            httpGet:
              path: /liveness
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 30
          readinessProbe:
            httpGet:
              path: /readiness
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 10
```

---

## Render Deployment

Render automatically monitors the `/health` endpoint. If it returns non-200, the service will be restarted.

### Environment Variables for Production

| Variable | Recommended Value |
|----------|-------------------|
| `APP_ENV` | `production` |
| `DATABASE_URL` | PostgreSQL connection string |
| `SECRET_KEY` | Random 64-character string |
| `CORS_ORIGINS` | Your frontend domain |

---

## Monitoring Stack

### Recommended Setup

```
┌─────────────────────────────────────────────────────────────────┐
│                      Monitoring Stack                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐      │
│  │   Render    │     │  Prometheus │     │   Grafana   │      │
│  │  (Backend)  │────►│  (Scrape)   │────►│  (Dashboards│      │
│  │             │     │             │     │   )         │      │
│  └─────────────┘     └─────────────┘     └─────────────┘      │
│        │                    │                    │               │
│        │              /metrics            Dashboard             │
│        │                                       URL               │
│        ▼                                                            │
│  ┌─────────────┐                                                 │
│  │  Health     │                                                 │
│  │  Endpoints  │                                                 │
│  │  /health    │                                                 │
│  │  /readiness │                                                 │
│  │  /system/   │                                                 │
│  │  status     │                                                 │
│  └─────────────┘                                                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Alerting Rules

### Recommended Alerts

| Alert | Condition | Severity |
|-------|-----------|----------|
| `BackendDown` | `/health` returns 5xx | Critical |
| `DatabaseDown` | `/readiness` returns 503 | Critical |
| `HighLatency` | p99 latency > 5s | Warning |
| `HighErrorRate` | 5xx rate > 1% | Warning |
| `AI ServiceDown` | AI calls 100% failed | Warning |

---

## Troubleshooting

### Check System Status

```bash
curl https://your-backend.onrender.com/system/status
```

### Check Database Connection

```bash
curl https://your-backend.onrender.com/readiness
```

### View All Metrics

```bash
curl https://your-backend.onrender.com/metrics
```

---

## Response Headers

All health endpoints include these headers:

| Header | Description |
|--------|-------------|
| `X-Request-ID` | Unique request identifier for tracing |
| `X-Process-Time` | Request processing time in seconds |

Example:
```
X-Request-ID: abc123-def456-ghi789
X-Process-Time: 0.0234
```
