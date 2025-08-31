"""
FastAPI RADIUS API - Test Version (without database)
For testing API functionality without database dependencies
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, status, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import logging

# Security Configuration
BEARER_TOKEN = os.getenv('API_KEY', 'your-secret-bearer-token-here')
security = HTTPBearer()

# Logging Configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mock data storage (in-memory)
mock_users = {}
mock_packages = {}
mock_accounting = {}
mock_nas = {}

# Pydantic Models
class PackageCreate(BaseModel):
    package: str = Field(..., min_length=1, max_length=64)
    pool: str = Field(..., min_length=1, max_length=253)
    profile: str = Field(..., min_length=1, max_length=253)

class UserCreate(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    passwd: str = Field(..., min_length=1, max_length=253)
    expdate: str = Field(..., description="Expiration date in YYYY-MM-DD format")
    package: str = Field(..., min_length=1, max_length=64)

class StatusResponse(BaseModel):
    message: str

class PaginatedResponse(BaseModel):
    count: int
    data: List[Any]

# Dependency Functions
async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if credentials.credentials != BEARER_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting RADIUS Management API (Test Mode)")
    
    # Initialize mock data
    mock_packages["basic_package"] = {
        "package": "basic_package",
        "pool": "basic_pool", 
        "profile": "basic_profile"
    }
    
    yield
    logger.info("Shutting down RADIUS Management API (Test Mode)")

# FastAPI App
app = FastAPI(
    title="RADIUS Management API (Test Mode)",
    description="FastAPI-based RADIUS management - Test version without database",
    version="2.0.0-test",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
@app.get("/", response_model=StatusResponse)
async def root():
    return StatusResponse(message="RADIUS Management API is running (Test Mode)")

# Package Management
@app.post("/package", response_model=StatusResponse, status_code=status.HTTP_201_CREATED)
async def create_package(
    package: PackageCreate,
    token: str = Depends(verify_token)
):
    """Create a new package with default attributes."""
    
    if package.package in mock_packages:
        raise HTTPException(status_code=400, detail="Package already exists")
    
    mock_packages[package.package] = {
        "package": package.package,
        "pool": package.pool,
        "profile": package.profile,
        "created": datetime.now().isoformat()
    }
    
    return StatusResponse(message="Package created successfully")

@app.get("/package/{limit}/{offset}", response_model=PaginatedResponse)
async def get_packages(
    limit: int,
    offset: int,
    token: str = Depends(verify_token)
):
    """Get paginated list of packages."""
    
    packages_list = list(mock_packages.keys())
    total_count = len(packages_list)
    
    # Apply pagination
    start_idx = offset
    end_idx = offset + limit
    paginated_packages = [{"groupname": pkg} for pkg in packages_list[start_idx:end_idx]]
    
    return PaginatedResponse(count=total_count, data=paginated_packages)

# User Management
@app.post("/user", response_model=StatusResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user: UserCreate,
    token: str = Depends(verify_token)
):
    """Create a new user."""
    
    if user.username in mock_users:
        raise HTTPException(status_code=400, detail="User already exists")
    
    if user.package not in mock_packages:
        raise HTTPException(status_code=400, detail="Package does not exist")
    
    mock_users[user.username] = {
        "username": user.username,
        "passwd": user.passwd,
        "expdate": user.expdate,
        "package": user.package,
        "created": datetime.now().isoformat()
    }
    
    return StatusResponse(message="User created successfully")

@app.get("/user/{username}")
async def get_user(
    username: str,
    token: str = Depends(verify_token)
):
    """Get specific user details."""
    
    if username not in mock_users:
        raise HTTPException(status_code=404, detail="User not found")
    
    user_data = mock_users[username]
    return {
        "logdata": [
            {"username": username, "value": user_data["passwd"]},
            {"username": username, "value": user_data["expdate"]}
        ]
    }

@app.delete("/user/{username}", response_model=StatusResponse)
async def delete_user(
    username: str,
    token: str = Depends(verify_token)
):
    """Delete a user."""
    
    if username not in mock_users:
        raise HTTPException(status_code=404, detail="User not found")
    
    del mock_users[username]
    # Also remove from accounting if exists
    if username in mock_accounting:
        del mock_accounting[username]
    
    return StatusResponse(message="User deleted successfully")

# Accounting
@app.get("/acct/{username}/{limit}/{offset}", response_model=PaginatedResponse)
async def get_user_accounting(
    username: str,
    limit: int,
    offset: int,
    token: str = Depends(verify_token)
):
    """Get user accounting records."""
    
    if username not in mock_users:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Generate mock accounting data
    mock_records = [
        {
            "radacctid": i,
            "username": username,
            "acctterminatecause": "User-Request" if i % 2 == 0 else "",
            "callingstationid": f"00:11:22:33:44:{50+i:02d}",
            "nasipaddress": "192.168.1.1",
            "acctstarttime": f"2024-08-{20+i:02d} 10:00:00",
            "acctupdatetime": f"2024-08-{20+i:02d} 11:30:00",
            "acctstoptime": f"2024-08-{20+i:02d} 12:00:00" if i % 2 == 0 else None,
            "acctsessiontime": 7200 if i % 2 == 0 else None,
            "acctinputoctets": 1024000 * (i + 1),
            "acctoutputoctets": 2048000 * (i + 1),
            "framedipaddress": f"10.0.1.{100+i}"
        }
        for i in range(5)  # Generate 5 mock records
    ]
    
    total_count = len(mock_records)
    start_idx = offset
    end_idx = offset + limit
    paginated_records = mock_records[start_idx:end_idx]
    
    return PaginatedResponse(count=total_count, data=paginated_records)

# Online Status
@app.get("/online")
async def get_online_users(token: str = Depends(verify_token)):
    """Get all online users."""
    
    # Mock online users
    online_users = []
    for username, user_data in mock_users.items():
        online_users.append({
            "radacctid": hash(username) % 10000,
            "username": username,
            "callingstationid": "00:11:22:33:44:55",
            "nasipaddress": "192.168.1.1",
            "acctstarttime": "2024-08-30 10:00:00",
            "framedipaddress": "10.0.1.100"
        })
    
    return online_users

@app.get("/onlinecount")
async def get_online_count(token: str = Depends(verify_token)):
    """Get count of online users."""
    
    return {"total_online": len(mock_users)}

@app.get("/online/{username}")
async def get_user_online_status(
    username: str,
    token: str = Depends(verify_token)
):
    """Check if specific user is online."""
    
    if username not in mock_users:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Mock: assume all users are online
    return {"status": "Online"}

# NAS Management
@app.post("/nas", response_model=StatusResponse)
async def create_nas(
    nasname: str = Query(...),
    shortname: str = Query(...),
    secret: str = Query(...),
    type: str = Query(default="other"),
    description: str = Query(default="RADIUS Client"),
    token: str = Depends(verify_token)
):
    """Create a new NAS."""
    
    if nasname in mock_nas:
        raise HTTPException(status_code=400, detail="NAS already exists")
    
    mock_nas[nasname] = {
        "nasname": nasname,
        "shortname": shortname,
        "secret": secret,
        "type": type,
        "description": description,
        "created": datetime.now().isoformat()
    }
    
    return StatusResponse(message="NAS created successfully")

# Session Disconnect
@app.post("/session-dis", response_model=StatusResponse)
async def disconnect_session(
    session: str = Query(...),
    nas: str = Query(...),
    token: str = Depends(verify_token)
):
    """Disconnect user session (mock implementation)."""
    
    # Mock implementation - just return success
    return StatusResponse(message="User session disconnected successfully (mock)")

# Health Check
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    
    return {
        "status": "healthy",
        "database": "mock (no database in test mode)",
        "timestamp": datetime.now().isoformat(),
        "mode": "test",
        "users_count": len(mock_users),
        "packages_count": len(mock_packages),
        "nas_count": len(mock_nas)
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("test_app:app", host="0.0.0.0", port=8000, reload=True)