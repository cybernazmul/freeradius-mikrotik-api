"""
FastAPI RADIUS API using raw MySQL queries (no ORM)
Lightweight alternative to SQLAlchemy
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
import os
import subprocess
from contextlib import asynccontextmanager
import mysql.connector
from mysql.connector import pooling

from fastapi import FastAPI, HTTPException, Depends, status, Query, Path, Path
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict
import logging

# Database Configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'radius-db'),
    'user': os.getenv('DB_USER', 'radius'),
    'password': os.getenv('DB_PASS', 'radiuspass'),
    'database': os.getenv('DB_NAME', 'radius'),
    'port': int(os.getenv('DB_PORT', '3306')),
    'autocommit': False,
    'charset': 'utf8mb4'
}

# Create connection pool
connection_pool = pooling.MySQLConnectionPool(
    pool_name="radius_pool",
    pool_size=10,
    pool_reset_session=True,
    **DB_CONFIG
)

# Security Configuration
BEARER_TOKEN = os.getenv('API_KEY', 'your-secret-bearer-token-here')
security = HTTPBearer()

# Logging Configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Pydantic Models
class PackageCreate(BaseModel):
    package: str = Field(..., min_length=1, max_length=64)
    pool: str = Field(..., min_length=1, max_length=253)

class UserCreate(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    passwd: str = Field(..., min_length=1, max_length=253)
    expdate: str = Field(..., description="Expiration date in YYYY-MM-DD format 30 Jun 2020 05:00:26")
    package: str = Field(..., min_length=1, max_length=64)

class StatusResponse(BaseModel):
    message: str

class PaginatedResponse(BaseModel):
    count: int
    data: List[Any]

# Database Connection Manager
class DatabaseManager:
    def __init__(self):
        self.pool = connection_pool
    
    def get_connection(self):
        return self.pool.get_connection()
    
    def execute_query(self, query: str, params: Optional[tuple] = None, fetch: bool = True):
        """Execute a query and return results"""
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, params if params is not None else ())
            
            if fetch:
                if query.strip().upper().startswith('SELECT'):
                    return cursor.fetchall()
                else:
                    conn.commit()
                    return cursor.rowcount
            else:
                conn.commit()
                return cursor.lastrowid
                
        except mysql.connector.Error as e:
            if conn:
                conn.rollback()
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def execute_transaction(self, queries: List[tuple]):
        """Execute multiple queries in a transaction"""
        conn = None
        cursor = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            for query, params in queries:
                cursor.execute(query, params if params is not None else ())
            
            conn.commit()
            return True
            
        except mysql.connector.Error as e:
            if conn:
                conn.rollback()
            raise HTTPException(status_code=500, detail=f"Transaction failed: {str(e)}")
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

# Initialize database manager
db_manager = DatabaseManager()

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
    logger.info("Starting RADIUS Management API")
    yield
    logger.info("Shutting down RADIUS Management API")

# FastAPI App
app = FastAPI(
    title="RADIUS Management API (Raw MySQL)",
    description="FastAPI-based RADIUS management with raw MySQL queries",
    version="2.0.0",
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
    return StatusResponse(message="RADIUS Management API is running")

# Package Management
@app.post("/package", response_model=StatusResponse, status_code=status.HTTP_201_CREATED)
async def create_package(
    package: PackageCreate,
    token: str = Depends(verify_token)
):
    """Create a new package with default attributes."""
    
    # Check if package exists
    check_query = "SELECT COUNT(*) as count FROM radgroupcheck WHERE groupname = %s"
    result = db_manager.execute_query(check_query, (package.package,))
    
    if result[0]['count'] > 0:
        raise HTTPException(status_code=400, detail="Package already exists")
    
    # Insert package attributes
    queries = [
        ("INSERT INTO radgroupcheck (groupname, attribute, op, value) VALUES (%s, %s, %s, %s)",
         (package.package, 'Simultaneous-Use', ':=', '1')),
        ("INSERT INTO radgroupreply (groupname, attribute, op, value) VALUES (%s, %s, %s, %s)",
         (package.package, 'Framed-Pool', '=', package.pool)),
        ("INSERT INTO radgroupreply (groupname, attribute, op, value) VALUES (%s, %s, %s, %s)",
         (package.package, 'Acct-Interim-Interval', '=', '120'))
    ]
    
    db_manager.execute_transaction(queries)
    return StatusResponse(message="Package created successfully")

@app.get("/package/{limit}/{offset}", response_model=PaginatedResponse)
async def get_packages(
    limit: int,
    offset: int,
    token: str = Depends(verify_token)
):
    """Get paginated list of packages."""
    
    # Get count
    count_query = "SELECT COUNT(DISTINCT groupname) as count FROM radgroupcheck"
    count_result = db_manager.execute_query(count_query)
    count = count_result[0]['count']
    
    # Get packages
    packages_query = """
        SELECT DISTINCT groupname 
        FROM radgroupcheck 
        GROUP BY groupname 
        LIMIT %s OFFSET %s
    """
    packages = db_manager.execute_query(packages_query, (limit, offset))
    
    return PaginatedResponse(count=count, data=packages)

# User Management
@app.post("/user", response_model=StatusResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user: UserCreate,
    token: str = Depends(verify_token)
):
    """Create a new user."""
    
    # Check if user exists
    check_query = "SELECT COUNT(*) as count FROM radcheck WHERE username = %s"
    result = db_manager.execute_query(check_query, (user.username,))
    
    if result[0]['count'] > 0:
        raise HTTPException(status_code=400, detail="User already exists")
    
    # Create user
    queries = [
        ("INSERT INTO radcheck (username, attribute, op, value) VALUES (%s, %s, %s, %s)",
         (user.username, 'Cleartext-Password', ':=', user.passwd)),
        ("INSERT INTO radcheck (username, attribute, op, value) VALUES (%s, %s, %s, %s)",
         (user.username, 'Expiration', ':=', user.expdate)),
        ("INSERT INTO radusergroup (username, groupname) VALUES (%s, %s)",
         (user.username, user.package))
    ]
    
    db_manager.execute_transaction(queries)
    return StatusResponse(message="User created successfully")

@app.get("/user/{username}")
async def get_user(
    username: str,
    token: str = Depends(verify_token)
):
    """Get specific user details."""
    
    query = "SELECT username, value FROM radcheck WHERE username = %s"
    users = db_manager.execute_query(query, (username,))
    
    if not users:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"logdata": users}

@app.delete("/user/{username}", response_model=StatusResponse)
async def delete_user(
    username: str,
    token: str = Depends(verify_token)
):
    """Delete a user."""
    
    # Check if user exists
    check_query = "SELECT COUNT(*) as count FROM radcheck WHERE username = %s"
    result = db_manager.execute_query(check_query, (username,))
    
    if result[0]['count'] == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Delete user
    queries = [
        ("DELETE FROM radcheck WHERE username = %s", (username,)),
        ("DELETE FROM radusergroup WHERE username = %s", (username,))
    ]
    
    db_manager.execute_transaction(queries)
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
    
    # Get count
    count_query = "SELECT COUNT(*) as count FROM radacct WHERE username = %s"
    count_result = db_manager.execute_query(count_query, (username,))
    count = count_result[0]['count']
    
    # Get records
    acct_query = """
        SELECT radacctid, username, acctterminatecause, callingstationid, 
               nasipaddress, acctstarttime, acctupdatetime, acctstoptime,
               acctsessiontime, acctinputoctets, acctoutputoctets, framedipaddress
        FROM radacct 
        WHERE username = %s 
        ORDER BY radacctid 
        LIMIT %s OFFSET %s
    """
    records = db_manager.execute_query(acct_query, (username, limit, offset))
    
    return PaginatedResponse(count=count, data=records)

# Online Status
@app.get("/online")
async def get_online_users(token: str = Depends(verify_token)):
    """Get all online users."""
    
    query = """
        SELECT radacctid, username, callingstationid, nasipaddress, 
               acctstarttime, framedipaddress
        FROM radacct 
        WHERE acctstoptime IS NULL
    """
    online_users = db_manager.execute_query(query)
    return online_users

@app.get("/onlinecount")
async def get_online_count(token: str = Depends(verify_token)):
    """Get count of online users."""
    
    query = "SELECT COUNT(*) as count FROM radacct WHERE acctstoptime IS NULL"
    result = db_manager.execute_query(query)
    return {"total_online": result[0]['count']}

@app.get("/online/{username}")
async def get_user_online_status(
    username: str,
    token: str = Depends(verify_token)
):
    """Check if specific user is online."""
    
    # Check if user exists
    user_query = "SELECT COUNT(*) as count FROM radcheck WHERE username = %s"
    user_result = db_manager.execute_query(user_query, (username,))
    
    if user_result[0]['count'] == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check online status
    online_query = """
        SELECT COUNT(*) as count 
        FROM radacct 
        WHERE username = %s AND acctstoptime IS NULL
    """
    online_result = db_manager.execute_query(online_query, (username,))
    
    status_msg = "Online" if online_result[0]['count'] > 0 else "Offline"
    return {"status": status_msg}

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
    
    # Check if NAS exists
    check_query = "SELECT COUNT(*) as count FROM nas WHERE nasname = %s"
    result = db_manager.execute_query(check_query, (nasname,))
    
    if result[0]['count'] > 0:
        raise HTTPException(status_code=400, detail="NAS already exists")
    
    # Create NAS
    insert_query = """
        INSERT INTO nas (nasname, shortname, type, secret, description) 
        VALUES (%s, %s, %s, %s, %s)
    """
    db_manager.execute_query(insert_query, (nasname, shortname, type, secret, description), fetch=False)
    
    return StatusResponse(message="NAS created successfully")

# Session Disconnect
@app.post("/session-dis", response_model=StatusResponse)
async def disconnect_session(
    session: str = Query(...),
    nas: str = Query(...),
    token: str = Depends(verify_token)
):
    """Disconnect user session using radclient."""
    
    try:
        cmd = f'echo Acct-Session-Id={session} | radclient -r 1 {nas}:3799 disconnect RGL@dmin321#'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            return StatusResponse(message="User session disconnected successfully")
        else:
            raise HTTPException(status_code=500, detail="Session disconnect failed")
    
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Session disconnect timeout")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Session disconnect failed: {str(e)}")

# Health Check
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        # Test database connection
        test_query = "SELECT 1"
        db_manager.execute_query(test_query)
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    return {
        "status": "healthy" if db_status == "connected" else "unhealthy",
        "database": db_status,
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)