# System Design Document

## Introduction

This document provides a detailed explanation of how data flows through the HR AI Platform system, from user interaction to data persistence.

---

## Authentication Flow

### Login Process

```
┌─────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  User   │     │  Frontend   │     │   Backend   │     │  Database   │
└─────────┘     └─────────────┘     └─────────────┘     └─────────────┘
    │                  │                  │                  │
    │  1. Enter        │                  │                  │
    │  email/password  │                  │                  │
    │──────────────►  │                  │                  │
    │                  │                  │                  │
    │                  │  2. POST         │                  │
    │                  │  /api/auth/login │                  │
    │                  │────────────────►│                  │
    │                  │                  │                  │
    │                  │                  │  3. Query        │
    │                  │                  │  user by email   │
    │                  │                  │────────────────►│
    │                  │                  │                  │
    │                  │                  │  4. Return      │
    │                  │                  │  user record    │
    │                  │                  │◄────────────────│
    │                  │                  │                  │
    │                  │                  │  5. Verify       │
    │                  │                  │  password        │
    │                  │                  │  (bcrypt)        │
    │                  │                  │                  │
    │                  │                  │  6. Generate     │
    │                  │                  │  JWT token       │
    │                  │                  │                  │
    │                  │  7. Return      │                  │
    │                  │  JWT + user     │                  │
    │                  │◄────────────────│                  │
    │                  │                  │                  │
    │  8. Store token │                  │                  │
    │  in localStorage│                  │                  │
    │◄───────────────│                  │                  │
    │                  │                  │                  │
```

### JWT Token Structure

```json
{
  "sub": "user_id",
  "email": "user@example.com",
  "role": "admin",
  "organization_id": "org_123",
  "exp": 1699999999,
  "iat": 1699900000
}
```

### Protected Request Flow

```
┌─────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  User   │     │  Frontend   │     │   Backend   │     │  Database   │
└─────────┘     └─────────────┘     └─────────────┘     └─────────────┘
    │                  │                  │                  │
    │  1. API Request  │                  │                  │
    │  (with JWT)     │                  │                  │
    │──────────────►  │                  │                  │
    │                  │                  │                  │
    │                  │  2. Request     │                  │
    │                  │  Bearer Token  │                  │
    │                  │────────────────►│                  │
    │                  │                  │                  │
    │                  │  3. Extract &   │                  │
    │                  │  validate JWT   │                  │
    │                  │                  │                  │
    │                  │  4. Get user   │                  │
    │                  │  from token    │                  │
    │                  │                  │                  │
    │                  │  5. Check      │                  │
    │                  │  permissions   │                  │
    │                  │                  │                  │
    │                  │  6. Process    │                  │
    │                  │  request       │                  │
    │                  │────────────────►│                  │
    │                  │                  │                  │
    │                  │  7. Return     │                  │
    │                  │  data          │                  │
    │                  │◄────────────────│                  │
    │                  │                  │                  │
    │  8. Update UI   │                  │                  │
    │◄───────────────│                  │                  │
```

---

## Employee Management Flow

### Create Employee

```
User fills form
     │
     ▼
Frontend validates input
     │
     ▼
POST /api/employees
     │
     ▼
┌─────────────────────────────────────────────┐
│           Backend Processing                 │
│                                              │
│  1. Auth check (valid JWT?)                  │
│  2. Permission check (can create employee?) │
│  3. Validate request body (Pydantic)        │
│  4. Create user account                     │
│  5. Create employee record                   │
│  6. Assign default role                      │
│  7. Log audit event                          │
└─────────────────────────────────────────────┘
     │
     ▼
Save to PostgreSQL
     │
     ▼
Return employee object
```

### Update Employee

```
PATCH /api/employees/{id}
     │
     ▼
┌─────────────────────────────────────────────┐
│           Backend Processing                 │
│                                              │
│  1. Auth check                              │
│  2. Find employee (404 if not found)        │
│  3. Check org match (security)              │
│  4. Permission check (HR/Admin only)        │
│  5. Validate update fields                  │
│  6. Update employee                         │
│  7. Log audit event                         │
└─────────────────────────────────────────────┘
     │
     ▼
Commit to database
     │
     ▼
Return updated employee
```

---

## AI-Powered Resume Analysis Flow

```
┌─────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   HR    │     │  Frontend   │     │   Backend   │     │  OpenRouter │
│  User   │     │             │     │             │     │   (AI)      │
└─────────┘     └─────────────┘     └─────────────┘     └─────────────┘
    │                  │                  │                  │
    │  Upload resume  │                  │                  │
    │  (PDF/DOCX)     │                  │                  │
    │──────────────►  │                  │                  │
    │                  │                  │                  │
    │                  │  Parse file     │                  │
    │                  │  extract text   │                  │
    │                  │───────────────► │                  │
    │                  │                  │                  │
    │                  │  POST /api/ai/  │                  │
    │                  │  resume/analyze │                  │
    │                  │────────────────►│                  │
    │                  │                  │                  │
    │                  │                  │  Extract text   │
    │                  │                  │  from document  │
    │                  │                  │                  │
    │                  │                  │  Build AI       │
    │                  │                  │  prompt         │
    │                  │                  │───────────────► │
    │                  │                  │                  │
    │                  │                  │  Call Gemini    │
    │                  │                  │  API            │
    │                  │                  │───────────────► │
    │                  │                  │                  │
    │                  │                  │  AI Response    │
    │                  │◄────────────────│                  │
    │                  │                  │                  │
    │                  │  Parse AI JSON   │                  │
    │                  │  response       │                  │
    │                  │                  │                  │
    │  Display        │                  │                  │
    │  results        │                  │                  │
    │◄───────────────│                  │                  │
```

### AI Analysis Response Structure

```json
{
  "candidate_name": "John Doe",
  "experience_years": 5,
  "skills": ["Python", "React", "PostgreSQL"],
  "education": "BS Computer Science",
  "strengths": [
    "Strong full-stack experience",
    "Cloud deployment knowledge"
  ],
  "concerns": [
    "Limited leadership experience"
  ],
  "recommendation": "highly_recommended",
  "score": 85
}
```

---

## Leave Request Workflow

```
┌─────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│Employee │     │  Frontend   │     │   Backend   │     │  Database   │
└─────────┘     └─────────────┘     └─────────────┘     └─────────────┘
    │                  │                  │                  │
    │  Submit leave   │                  │                  │
    │  request       │                  │                  │
    │──────────────► │                  │                  │
    │                  │                  │                  │
    │                  │  POST /api/leave │                  │
    │                  │  /requests      │                  │
    │                  │────────────────►│                  │
    │                  │                  │                  │
    │                  │                  │  1. Validate   │
    │                  │                  │  balance        │
    │                  │                  │                  │
    │                  │                  │  2. Create      │
    │                  │                  │  request        │
    │                  │                  │────────────────►│
    │                  │                  │                  │
    │                  │                  │  3. Create      │
    │                  │                  │  notification   │
    │                  │                  │────────────────►│
    │                  │                  │                  │
    │                  │  Return         │                  │
    │                  │◄────────────────│                  │
    │                  │                  │                  │
    │  Show pending   │                  │                  │
    │◄───────────────│                  │                  │
                                                  │
                                                  ▼
                              ┌─────────────────────────────────┐
                              │      Approval Workflow          │
                              │                                  │
                              │  Employee → Manager → HR → Done │
                              │                                  │
                              │  Each level:                    │
                              │  1. Review request              │
                              │  2. Approve/Reject               │
                              │  3. Notify employee             │
                              │  4. Update balance               │
                              └─────────────────────────────────┘
```

---

## Payroll Processing Flow

```
┌─────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   HR    │     │  Frontend   │     │   Backend   │     │  Database   │
│  Admin  │     │             │     │             │     │             │
└─────────┘     └─────────────┘     └─────────────┘     └─────────────┘
    │                  │                  │                  │
    │  Initiate       │                  │                  │
    │  payroll run    │                  │                  │
    │──────────────► │                  │                  │
    │                  │                  │                  │
    │                  │  POST /api/     │                  │
    │                  │  payroll/run    │                  │
    │                  │────────────────►│                  │
    │                  │                  │                  │
    │                  │                  │  ┌────────────┐  │
    │                  │                  │  │ For each  │  │
    │                  │                  │  │ employee: │  │
    │                  │                  │  │           │  │
    │                  │                  │  │ 1. Get   │  │
    │                  │                  │  │ salary   │  │
    │                  │                  │  │ components│  │
    │                  │                  │  │           │  │
    │                  │                  │  │ 2. Calc  │  │
    │                  │                  │  │ deductions│ │
    │                  │                  │  │           │  │
    │                  │                  │  │ 3. Calc  │  │
    │                  │                  │  │ taxes    │  │
    │                  │                  │  │           │  │
    │                  │                  │  │ 4. Calc  │  │
    │                  │                  │  │ net pay  │  │
    │                  │                  │  │           │  │
    │                  │                  │  │ 5. Create│  │
    │                  │                  │  │ record   │  │
    │                  │                  │  └────────────┘  │
    │                  │                  │                  │
    │                  │                  │  Save all       │
    │                  │                  │  payroll records│
    │                  │                  │────────────────►│
    │                  │                  │                  │
    │                  │  Return         │                  │
    │                  │  summary        │                  │
    │                  │◄────────────────│                  │
    │                  │                  │                  │
    │  Show payroll   │                  │                  │
    │  summary        │                  │                  │
    │◄───────────────│                  │                  │
```

---

## Document Upload Flow

```
┌─────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│Employee │     │  Frontend   │     │   Backend   │     │  File System│
└─────────┘     └─────────────┘     └─────────────┘     └─────────────┘
    │                  │                  │                  │
    │  Upload        │                  │                  │
    │  document      │                  │                  │
    │──────────────► │                  │                  │
    │                  │                  │                  │
    │                  │  Validate file  │                  │
    │                  │  type & size    │                  │
    │                  │                  │                  │
    │                  │  POST /api/     │                  │
    │                  │  documents/    │                  │
    │                  │  upload         │                  │
    │                  │────────────────►│                  │
    │                  │                  │                  │
    │                  │                  │  Generate       │
    │                  │                  │  unique filename│
    │                  │                  │                  │
    │                  │                  │  Save to        │
    │                  │                  │  uploads/       │
    │                  │                  │───────────────► │
    │                  │                  │                  │
    │                  │                  │  Create DB      │
    │                  │                  │  record         │
    │                  │                  │────────────────►│
    │                  │                  │                  │
    │                  │  Return         │                  │
    │                  │  document info  │                  │
    │                  │◄────────────────│                  │
    │                  │                  │                  │
    │  Show upload   │                  │                  │
    │  success       │                  │                  │
    │◄───────────────│                  │                  │
```

---

## Error Handling Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Error Handling                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐       │
│  │   Client     │────►│   FastAPI     │────►│   Service    │       │
│  │   Request    │     │   Layer       │     │   Layer      │       │
│  └──────────────┘     └──────────────┘     └──────────────┘       │
│         │                    │                     │              │
│         │                    │ Exception            │              │
│         │              ◄─────┴───────              │              │
│         │                    │                     │              │
│         │                    ▼                     │              │
│         │              ┌──────────────┐          │              │
│         │              │   Exception   │          │              │
│         │              │   Handler     │          │              │
│         │              └──────────────┘          │              │
│         │                    │                     │              │
│         │                    ▼                     │              │
│         │              ┌──────────────┐          │              │
│         │              │  Log Error   │          │              │
│         │              │  (JSON)      │          │              │
│         │              └──────────────┘          │              │
│         │                    │                     │              │
│         │                    ▼                     │              │
│         │              ┌──────────────┐          │              │
│         │              │  Return      │          │              │
│         │              │  Error JSON  │          │              │
│         │              └──────────────┘          │              │
│         │                    │                     │              │
│         ▼                    ▼                     ▼              │
│  ┌──────────────────────────────────────────────────────────┐     │
│  │                    Error Response                         │     │
│  │  {                                                       │     │
│  │    "success": false,                                     │     │
│  │    "errors": [{"msg": "...", "code": "ERROR_CODE"}]     │     │
│  │  }                                                       │     │
│  └──────────────────────────────────────────────────────────┘     │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Data Consistency & Transactions

### Database Transaction Pattern

```python
# Example: Creating an employee with user account
with SessionLocal() as session:
    try:
        # Start transaction
        session.begin()
        
        # Create user
        user = User(email=email, password_hash=hash)
        session.add(user)
        session.flush()  # Get user ID
        
        # Create employee
        employee = Employee(
            user_id=user.id,
            organization_id=org_id,
            department_id=department_id,
            ...
        )
        session.add(employee)
        
        # Commit transaction
        session.commit()
        
    except Exception as e:
        # Rollback on error
        session.rollback()
        raise
```

---

## Audit Logging

Every significant action is logged for compliance:

| Event Type | Logged Fields |
|------------|---------------|
| Create | user_id, action, resource_type, resource_id, changes |
| Update | user_id, action, resource_type, resource_id, old_values, new_values |
| Delete | user_id, action, resource_type, resource_id |
| Login | user_id, ip_address, user_agent |
| Logout | user_id, session_duration |
| Permission Denied | user_id, requested_resource, required_role |

---

## Monitoring & Observability

### Request Lifecycle Logging

```
Incoming Request
       │
       ▼
Correlation ID Added
       │
       ▼
Request Logged (method, path, client IP)
       │
       ▼
Authentication Check
       │
       ▼
Permission Check
       │
       ▼
Business Logic Execution
       │
       ▼
Database Query
       │
       ▼
Response Logged (status, duration)
       │
       ▼
Response Sent
```

### Metrics Collected

- **Request Count**: Total requests by endpoint, method, status
- **Latency**: Request duration histogram
- **Error Rate**: Failed requests per endpoint
- **AI Service**: AI API call success/failure
- **Database**: Query performance
