from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import init_db
from app.routers import helpdesk, resume, risk, interview, documents, onboarding, leave, payroll, burnout
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

app = FastAPI(title="HR AI Platform")

# CORS middleware for frontend - allow both ports
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database
@app.on_event("startup")
def startup_event():
    init_db()

# Include routers
app.include_router(helpdesk.router)
app.include_router(resume.router)
app.include_router(risk.router)
app.include_router(interview.router)
app.include_router(documents.router)
app.include_router(onboarding.router)
app.include_router(leave.router)
app.include_router(payroll.router)
app.include_router(burnout.router)

@app.get("/")
def root():
    return {"message": "HR AI Platform API"}