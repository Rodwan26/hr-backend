# HR AI Management System - Backend

An intelligent HR management platform that helps companies manage employees, recruitment, payroll, onboarding, and AI-powered HR insights.

## Features

- **Employee Management** - Complete CRUD operations for employee records
- **Recruitment & Resume Tracking** - AI-powered resume parsing and candidate evaluation
- **Payroll Management** - Automated payroll processing with multiple salary components
- **AI-Powered HR Insights** - AI-driven analysis for burnout detection, risk assessment, and recommendations
- **Document Management** - Secure document upload, storage, and version control
- **Risk & Burnout Monitoring** - Proactive monitoring of employee wellbeing
- **Leave Management** - Multi-level leave approval workflow
- **Onboarding Automation** - Streamlined employee onboarding with AI assistant
- **Secure Authentication** - JWT-based auth with role-based access control (RBAC)
- **Audit Logging** - Complete audit trail for compliance

## Tech Stack

### Backend
- **FastAPI** - Modern Python web framework
- **PostgreSQL** - Production-grade relational database
- **SQLAlchemy** - SQL toolkit and ORM
- **Alembic** - Database migrations
- **JWT** - Secure token-based authentication
- **Pydantic** - Data validation
- **Python-Jose** - JWT handling

### Infrastructure
- **Render** - Backend hosting
- **PostgreSQL** - Database (Render)

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (Next.js)                       │
│                    https://github.com/Rodwan26/hr-frontend       │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
                    ┌─────────────────────────────┐
                    │     API Gateway (FastAPI)    │
                    │        /api/v1/*            │
                    └─────────────────────────────┘
                                  │
            ┌─────────────────────┼─────────────────────┐
            ▼                     ▼                     ▼
   ┌──────────────┐    ┌──────────────────┐    ┌──────────────┐
   │   Services   │    │   AI Services   │    │  Database   │
   │  (Business   │    │  (OpenRouter)   │    │ (PostgreSQL)│
   │    Logic)    │    │                 │    │             │
   └──────────────┘    └──────────────────┘    └──────────────┘
```

## API Endpoints

### Health Check Endpoints
| Endpoint | Description |
|----------|-------------|
| `GET /health` | Basic liveness probe |
| `GET /readiness` | Database connectivity check |
| `GET /liveness` | Alias for /health |
| `GET /metrics` | Prometheus metrics |
| `GET /system/status` | Comprehensive system status |

### Authentication
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/login` | POST | User login |
| `/api/auth/register` | POST | User registration |
| `/api/auth/refresh` | POST | Refresh JWT token |
| `/api/auth/logout` | POST | User logout |

### Core HR Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/employees` | GET/POST | List/Create employees |
| `/api/employees/{id}` | GET/PUT/DELETE | Employee operations |
| `/api/departments` | GET/POST | Department management |
| `/api/jobs` | GET/POST | Job postings |
| `/api/resumes` | GET/POST | Resume management |

### AI-Powered Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/ai/resume/analyze` | POST | AI resume analysis |
| `/api/ai/interview/generate` | POST | Generate interview questions |
| `/api/ai/burnout/analyze` | POST | Burnout risk assessment |
| `/api/ai/risk/analyze` | POST | Employee risk analysis |
| `/api/ai/onboarding/chat` | POST | AI onboarding assistant |

### Payroll & Leave
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/payroll/run` | POST | Execute payroll |
| `/api/leave/requests` | GET/POST | Leave requests |
| `/api/leave/approve` | POST | Approve leave request |

## Health Check Response

```json
GET /system/status

{
  "status": "healthy",
  "version": "1.0.0",
  "environment": "production",
  "timestamp": "2026-03-16T12:00:00Z",
  "components": {
    "database": {
      "status": "connected",
      "version": "PostgreSQL 15.x"
    },
    "ai_service": {
      "status": "configured",
      "model": "google/gemini-2.0-flash-001"
    },
    "security": {
      "rate_limiting": "enabled",
      "csrf_protection": "enabled"
    }
  }
}
```

## Getting Started

### Prerequisites
- Python 3.10+
- PostgreSQL 15+

### Installation

1. Clone the repository
```bash
git clone https://github.com/Rodwan26/hr-backend.git
cd hr-backend
```

2. Create virtual environment
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows
```

3. Install dependencies
```bash
pip install -r requirements.txt
```

4. Configure environment variables
```bash
cp .env.example .env
# Edit .env with your settings
```

5. Run database migrations
```bash
alembic upgrade head
```

6. Start the server
```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`
- API Docs: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `sqlite:///./database.db` |
| `SECRET_KEY` | JWT secret key | (dev only) |
| `OPENROUTER_API_KEY` | AI service API key | Required for AI features |
| `AI_MODEL_NAME` | AI model to use | `google/gemini-2.0-flash-001` |
| `APP_ENV` | Environment | `development` |
| `CORS_ORIGINS` | Allowed origins | localhost |

## Project Structure

```
backend/
├── app/
│   ├── core/           # Core configurations
│   │   ├── config.py   # Settings
│   │   ├── security.py # JWT & auth
│   │   ├── logging.py  # JSON logging
│   │   ├── metrics.py  # Prometheus metrics
│   │   └── middleware.py
│   ├── models/         # SQLAlchemy models
│   ├── routers/        # API endpoints
│   ├── services/       # Business logic
│   ├── schemas/        # Pydantic schemas
│   └── main.py        # FastAPI app
├── alembic/           # Database migrations
├── tests/             # Test suite
└── requirements.txt
```

## Security Features

- JWT token authentication
- Role-based access control (RBAC)
- Rate limiting (60 req/min)
- CORS protection
- CSRF protection (production)
- Security headers (HSTS, CSP, etc.)
- SQL injection prevention
- XSS protection
- Audit logging

## Monitoring & Observability

- **Health Checks**: `/health`, `/readiness`, `/liveness`
- **System Status**: `/system/status`
- **Metrics**: `/metrics` (Prometheus format)
- **Request Logging**: JSON format with correlation IDs
- **Error Tracking**: Structured exception handling

## Deployment

### Backend (Render)
1. Connect GitHub repository to Render
2. Set environment variables
3. Render will automatically deploy

### Database (Render PostgreSQL)
1. Create PostgreSQL service on Render
2. Get connection string
3. Set as DATABASE_URL in backend

## API Documentation

- **Swagger UI**: `/docs`
- **ReDoc**: `/redoc`
- **OpenAPI Schema**: `/openapi.json`

## Author

**Radwan Benmoussa** - Full Stack Developer

- GitHub: [@Rodwan26](https://github.com/Rodwan26)
- Frontend Repo: [hr-frontend](https://github.com/Rodwan26/hr-frontend)

## License

MIT License

---

<div align="center">

**[API Docs](https://hr-backend.onrender.com/docs)** •
**[Live Demo](https://hr-frontend.vercel.app)** •
**[Report Bug](https://github.com/Rodwan26/hr-backend/issues)**

</div>
