# System Architecture

## Overview

The HR AI Platform follows a modern three-tier architecture pattern designed for scalability, maintainability, and separation of concerns.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                                   │
│                                                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    Next.js Frontend                                  │    │
│  │                  (React + TypeScript)                               │    │
│  │                                                                     │    │
│  │  • User Interface                                                   │    │
│  │  • State Management (Zustand)                                      │    │
│  │  • API Integration                                                  │    │
│  │  • Form Validation                                                  │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ HTTPS (REST API)
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                             API GATEWAY LAYER                               │
│                                                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                   FastAPI Backend                                    │    │
│  │                                                                     │    │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐  │    │
│  │  │   Auth      │ │   Employees │ │   Payroll   │ │   AI        │  │    │
│  │  │   Router    │ │   Router    │ │   Router    │ │   Router    │  │    │
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘  │    │
│  │                                                                     │    │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐  │    │
│  │  │   Leave     │ │   Jobs      │ │  Documents  │ │  Onboarding │  │    │
│  │  │   Router    │ │   Router    │ │   Router    │ │   Router    │  │    │
│  │  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘  │    │
│  │                                                                     │    │
│  │  ┌─────────────────────────────────────────────────────────────┐   │    │
│  │  │                    Middleware Stack                          │   │    │
│  │  │  CORS → Logging → Performance → Security → CSRF → RateLimit │   │    │
│  │  └─────────────────────────────────────────────────────────────┘   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATA LAYER                                      │
│                                                                            │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐     │
│  │   PostgreSQL    │  │    Services     │  │      External AI        │     │
│  │   Database     │  │   (Business     │  │      Services           │     │
│  │                 │  │    Logic)       │  │   (OpenRouter/Gemini)   │     │
│  │  • Employees    │  │                 │  │                         │     │
│  │  • Payroll      │  │  • AuthService  │  │  • Resume Analysis      │     │
│  │  • Leave        │  │  • LeaveService │  │  • Interview Questions  │     │
│  │  • Documents    │  │  • PayrollSvc  │  │  • Burnout Detection    │     │
│  │  • Audit Logs   │  │  • AIService    │  │  • Risk Assessment      │     │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────────┘     │
│                                                                            │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Component Diagram

### Backend Services

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         FastAPI Application                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                      Request Flow                                │    │
│  │                                                                  │    │
│  │   HTTP Request                                                   │    │
│  │        │                                                         │    │
│  │        ▼                                                         │    │
│  │   ┌─────────────┐                                               │    │
│  │   │  CORS       │ ◄── Validate Origin                          │    │
│  │   │  Middleware │                                               │    │
│  │   └─────────────┘                                               │    │
│  │        │                                                         │    │
│  │        ▼                                                         │    │
│  │   ┌─────────────┐                                               │    │
│  │   │  Logging    │ ◄── JSON logging with correlation ID        │    │
│  │   │  Middleware │                                               │    │
│  │   └─────────────┘                                               │    │
│  │        │                                                         │    │
│  │        ▼                                                         │    │
│  │   ┌─────────────┐                                               │    │
│  │   │  Rate       │ ◄── 60 requests/minute                       │    │
│  │   │  Limiter    │                                               │    │
│  │   └─────────────┘                                               │    │
│  │        │                                                         │    │
│  │        ▼                                                         │    │
│  │   ┌─────────────┐                                               │    │
│  │   │  Auth       │ ◄── Verify JWT token                         │    │
│  │   │  Dependency │                                               │    │
│  │   └─────────────┘                                               │    │
│  │        │                                                         │    │
│  │        ▼                                                         │    │
│  │   ┌─────────────┐                                               │    │
│  │   │  Router     │ ◄── Route to handler                         │    │
│  │   │  Handler    │                                               │    │
│  │   └─────────────┘                                               │    │
│  │        │                                                         │    │
│  │        ▼                                                         │    │
│  │   ┌─────────────┐                                               │    │
│  │   │  Service    │ ◄── Business logic                           │    │
│  │   │  Layer      │                                               │    │
│  │   └─────────────┘                                               │    │
│  │        │                                                         │    │
│  │        ▼                                                         │    │
│  │   ┌─────────────┐                                               │    │
│  │   │  Database   │ ◄── SQLAlchemy ORM                          │    │
│  │   │  Layer      │                                               │    │
│  │   └─────────────┘                                               │    │
│  │                                                                  │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Database Schema Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         PostgreSQL Database                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐   │
│  │   organizations │     │     users       │     │   employees     │   │
│  │   (PK: id)      │◄────│ (FK: org_id)    │◄────│ (FK: user_id)  │   │
│  │                 │     │ (PK: id)        │     │ (PK: id)        │   │
│  └─────────────────┘     └─────────────────┘     └─────────────────┘   │
│          │                       │                       │              │
│          │                       │                       │              │
│          ▼                       ▼                       ▼              │
│  ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐   │
│  │  departments    │     │    roles        │     │   user_roles    │   │
│  │ (FK: org_id)    │     │    (PK: id)     │     │                 │   │
│  └─────────────────┘     └─────────────────┘     └─────────────────┘   │
│                                                          │              │
│                                                          ▼              │
│  ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐   │
│  │  leave_requests │     │  payroll_run    │     │   resumes       │   │
│  │ (FK: employee)  │     │ (FK: employee)  │     │ (FK: employee)  │   │
│  └─────────────────┘     └─────────────────┘     └─────────────────┘   │
│                                                                          │
│  ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐   │
│  │  documents      │     │  audit_logs     │     │  onboarding_    │   │
│  │ (FK: employee)  │     │ (FK: user_id)   │     │  employees      │   │
│  └─────────────────┘     └─────────────────┘     └─────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Security Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Security Layers                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  Layer 1: Network Security                                               │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  • HTTPS/TLS (Render handles)                                   │    │
│  │  • CORS whitelist                                               │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                    │                                     │
│  Layer 2: Application Security                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  • JWT Authentication                                          │    │
│  │  • Role-Based Access Control (RBAC)                            │    │
│  │  • Password hashing (bcrypt)                                   │    │
│  │  • Rate limiting (60 req/min)                                  │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                    │                                     │
│  Layer 3: Data Security                                                │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  • SQL injection prevention (SQLAlchemy)                      │    │
│  │  • Input validation (Pydantic)                                 │    │
│  │  • Audit logging                                               │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                    │                                     │
│  Layer 4: Response Security                                            │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  • Security Headers (CSP, HSTS, X-Frame-Options)              │    │
│  │  • CSRF protection (production)                                │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Deployment Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Production Deployment                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌─────────────┐          ┌─────────────┐          ┌─────────────┐     │
│   │   Vercel    │          │   Render    │          │   Render    │     │
│   │  (Frontend) │─────────►│  (Backend)  │─────────►│  (PostgreSQL│     │
│   │             │  HTTPS   │             │   JDBC   │   )         │     │
│   └─────────────┘          └─────────────┘          └─────────────┘     │
│        │                        │                        │              │
│        │                        │                        │              │
│        ▼                        ▼                        ▼              │
│   Static Files              FastAPI                   PostgreSQL        │
│   (CDN)                    (Gunicorn)                (Managed)         │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Technology Stack Summary

| Layer | Technology | Purpose |
|-------|------------|---------|
| Frontend | Next.js 14 | React framework with SSR |
| Frontend | TypeScript | Type safety |
| Frontend | TailwindCSS | Styling |
| Frontend | Zustand | State management |
| Backend | FastAPI | REST API framework |
| Backend | Python 3.14 | Runtime |
| Database | PostgreSQL | Relational data |
| ORM | SQLAlchemy | Database abstraction |
| Migrations | Alembic | Schema versioning |
| Auth | JWT | Token-based auth |
| AI | OpenRouter | AI service gateway |
| Deployment | Render | Cloud hosting |
