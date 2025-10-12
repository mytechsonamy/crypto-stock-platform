# Security Guide

Security best practices and guidelines for the Crypto-Stock Platform.

## Table of Contents

- [Authentication](#authentication)
- [Authorization](#authorization)
- [API Security](#api-security)
- [Data Protection](#data-protection)
- [Network Security](#network-security)
- [Secrets Management](#secrets-management)
- [Security Best Practices](#security-best-practices)
- [Vulnerability Reporting](#vulnerability-reporting)

## Authentication

### JWT Token Authentication

The platform uses JWT (JSON Web Tokens) for authentication.

**Token Structure**:
```json
{
  "sub": "user_id",
  "email": "user@example.com",
  "role": "user",
  "exp": 1704067200,
  "iat": 1704063600
}
```

**Token Lifecycle**:
1. User logs in with credentials
2. Server validates credentials
3. Server generates JWT token (60-minute expiration)
4. Client stores token securely
5. Client includes token in requests
6. Server validates token on each request
7. Token expires after 60 minutes
8. Client requests new token via refresh endpoint

**Implementation**:
```python
# api/auth.py
from jose import JWTError, jwt
from datetime import datetime, timedelta

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=60))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
```

**Usage**:
```bash
# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password"}'

# Response
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600
}

# Use token
curl http://localhost:8000/api/v1/charts/BTCUSDT \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### Password Security

**Requirements**:
- Minimum 8 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one number
- At least one special character

**Hashing**:
```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)
```

### WebSocket Authentication

WebSocket connections require JWT token authentication:

```javascript
// Frontend
const token = localStorage.getItem('access_token');
const ws = new WebSocket(`ws://localhost:8000/ws/BTCUSDT?token=${token}`);

ws.onopen = () => {
  console.log('Connected');
};

ws.onerror = (error) => {
  if (error.code === 4001) {
    console.error('Authentication failed');
  }
};
```

```python
# Backend
async def authenticate_websocket(websocket: WebSocket, token: str):
    try:
        payload = verify_token(token)
        return payload
    except:
        await websocket.close(code=4001, reason="Authentication failed")
        return None
```

## Authorization

### Role-Based Access Control (RBAC)

**Roles**:
- **admin**: Full access to all resources
- **user**: Access to own data and public endpoints
- **readonly**: Read-only access

**Implementation**:
```python
from enum import Enum
from fastapi import Depends, HTTPException

class Role(str, Enum):
    ADMIN = "admin"
    USER = "user"
    READONLY = "readonly"

def check_permission(required_role: Role):
    def permission_checker(current_user: dict = Depends(get_current_user)):
        user_role = Role(current_user.get("role"))
        
        if user_role == Role.ADMIN:
            return current_user
        
        if required_role == Role.USER and user_role in [Role.USER, Role.ADMIN]:
            return current_user
        
        if required_role == Role.READONLY:
            return current_user
        
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    return permission_checker

# Usage
@app.get("/api/v1/admin/users")
async def get_users(user: dict = Depends(check_permission(Role.ADMIN))):
    # Only admins can access
    pass
```

### Resource-Level Authorization

```python
async def check_resource_access(user_id: int, resource_id: int):
    # Check if user owns the resource
    resource = await db.fetch_one(
        "SELECT user_id FROM resources WHERE id = $1",
        resource_id
    )
    
    if resource["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
```

## API Security

### Rate Limiting

**Token Bucket Algorithm**:
- 100 requests per minute per client
- Burst capacity: 20 requests
- Refill rate: 100 tokens/minute

**Implementation**:
```python
# api/rate_limiter.py
class TokenBucketRateLimiter:
    def __init__(self, rate: int = 100, period: int = 60):
        self.rate = rate
        self.period = period
        self.redis = redis.Redis()
    
    async def is_allowed(self, client_id: str) -> bool:
        key = f"rate_limit:{client_id}"
        
        # Get current tokens
        tokens = await self.redis.get(key)
        if tokens is None:
            tokens = self.rate
        else:
            tokens = int(tokens)
        
        # Check if request is allowed
        if tokens > 0:
            await self.redis.decr(key)
            await self.redis.expire(key, self.period)
            return True
        
        return False
```

**Response Headers**:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1704067200
Retry-After: 30
```

### CORS Configuration

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://yourdomain.com"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
    max_age=3600
)
```

### Input Validation

**Pydantic Models**:
```python
from pydantic import BaseModel, validator, Field

class ChartRequest(BaseModel):
    symbol: str = Field(..., regex="^[A-Z0-9]{3,20}$")
    timeframe: str = Field(..., regex="^(1m|5m|15m|1h|4h|1d)$")
    limit: int = Field(100, ge=1, le=5000)
    
    @validator('symbol')
    def validate_symbol(cls, v):
        if not v.isupper():
            raise ValueError('Symbol must be uppercase')
        return v
```

### SQL Injection Prevention

**Use Parameterized Queries**:
```python
# ✅ SAFE - Parameterized query
async def get_candles(symbol: str, timeframe: str):
    query = """
        SELECT * FROM candles
        WHERE symbol = $1 AND timeframe = $2
        ORDER BY time DESC
        LIMIT 100
    """
    return await db.fetch(query, symbol, timeframe)

# ❌ UNSAFE - String concatenation
async def get_candles_unsafe(symbol: str):
    query = f"SELECT * FROM candles WHERE symbol = '{symbol}'"  # DON'T DO THIS!
    return await db.fetch(query)
```

### XSS Prevention

**Content Security Policy**:
```python
from fastapi.responses import Response

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response
```

## Data Protection

### Encryption at Rest

**Database Encryption**:
```yaml
# docker-compose.yml
services:
  timescaledb:
    environment:
      POSTGRES_INITDB_ARGS: "--data-checksums"
    volumes:
      - type: volume
        source: db_data
        target: /var/lib/postgresql/data
        volume:
          driver_opts:
            type: "nfs"
            o: "encryption=aes256"
```

**Backup Encryption**:
```bash
# Encrypt backup with GPG
gpg --symmetric --cipher-algo AES256 backup.sql

# Decrypt backup
gpg --decrypt backup.sql.gpg > backup.sql
```

### Encryption in Transit

**HTTPS/TLS**:
```nginx
server {
    listen 443 ssl http2;
    server_name api.yourdomain.com;
    
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    
    location / {
        proxy_pass http://api:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

**WebSocket Secure (WSS)**:
```javascript
const ws = new WebSocket('wss://api.yourdomain.com/ws/BTCUSDT');
```

### Sensitive Data Handling

**Environment Variables**:
```bash
# ✅ GOOD - Use environment variables
DB_PASSWORD=${DB_PASSWORD}
JWT_SECRET=${JWT_SECRET}

# ❌ BAD - Hardcoded secrets
DB_PASSWORD=mypassword123
JWT_SECRET=mysecret
```

**Logging**:
```python
# ✅ GOOD - Mask sensitive data
logger.info(f"User logged in: {email}")

# ❌ BAD - Log sensitive data
logger.info(f"User logged in: {email}, password: {password}")
```

## Network Security

### Firewall Rules

**Allow only necessary ports**:
```bash
# Allow HTTP/HTTPS
ufw allow 80/tcp
ufw allow 443/tcp

# Allow SSH (from specific IP)
ufw allow from 203.0.113.0/24 to any port 22

# Deny all other incoming
ufw default deny incoming
ufw default allow outgoing

# Enable firewall
ufw enable
```

### Docker Network Isolation

```yaml
# docker-compose.yml
networks:
  frontend:
    driver: bridge
  backend:
    driver: bridge
    internal: true  # No external access

services:
  api:
    networks:
      - frontend
      - backend
  
  timescaledb:
    networks:
      - backend  # Only accessible from backend network
```

### DDoS Protection

**Rate Limiting**:
- API rate limiting (100 req/min)
- WebSocket connection limits
- Request size limits

**Cloudflare Protection**:
- Enable Cloudflare proxy
- Configure rate limiting rules
- Enable DDoS protection
- Use Web Application Firewall (WAF)

## Secrets Management

### Environment Variables

```bash
# .env (never commit to git)
DB_PASSWORD=<STRONG_PASSWORD>
JWT_SECRET=<RANDOM_256_BIT_SECRET>
BINANCE_API_SECRET=<API_SECRET>
```

### Docker Secrets

```bash
# Create secrets
echo "my_db_password" | docker secret create db_password -
echo "my_jwt_secret" | docker secret create jwt_secret -

# Use in docker-compose.yml
services:
  api:
    secrets:
      - db_password
      - jwt_secret
    environment:
      DB_PASSWORD_FILE: /run/secrets/db_password
      JWT_SECRET_FILE: /run/secrets/jwt_secret

secrets:
  db_password:
    external: true
  jwt_secret:
    external: true
```

### HashiCorp Vault

```python
import hvac

# Connect to Vault
client = hvac.Client(url='http://vault:8200', token='<TOKEN>')

# Read secret
secret = client.secrets.kv.v2.read_secret_version(path='crypto-stock/db')
db_password = secret['data']['data']['password']
```

### Kubernetes Secrets

```bash
# Create secret
kubectl create secret generic crypto-stock-secrets \
  --from-literal=db-password=<PASSWORD> \
  --from-literal=jwt-secret=<SECRET> \
  -n crypto-stock

# Use in pod
env:
  - name: DB_PASSWORD
    valueFrom:
      secretKeyRef:
        name: crypto-stock-secrets
        key: db-password
```

## Security Best Practices

### 1. Keep Dependencies Updated

```bash
# Check for vulnerabilities
pip install safety
safety check

# Update dependencies
pip install --upgrade -r requirements.txt
```

### 2. Use Strong Passwords

```python
import secrets
import string

def generate_password(length=32):
    alphabet = string.ascii_letters + string.digits + string.punctuation
    return ''.join(secrets.choice(alphabet) for _ in range(length))

# Generate JWT secret
jwt_secret = secrets.token_urlsafe(32)
```

### 3. Implement Audit Logging

```python
async def audit_log(user_id: int, action: str, resource: str, details: dict):
    await db.execute(
        """
        INSERT INTO audit_log (user_id, action, resource, details, timestamp)
        VALUES ($1, $2, $3, $4, NOW())
        """,
        user_id, action, resource, json.dumps(details)
    )

# Usage
await audit_log(user.id, "DELETE", "alert", {"alert_id": alert_id})
```

### 4. Regular Security Audits

- Review access logs
- Check for suspicious activity
- Update security policies
- Perform penetration testing
- Review code for vulnerabilities

### 5. Principle of Least Privilege

- Grant minimum necessary permissions
- Use separate accounts for different services
- Rotate credentials regularly
- Revoke unused access

### 6. Secure Configuration

```python
# config/settings.py
class Settings(BaseSettings):
    # Security settings
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_MINUTES: int = 60
    
    # Password requirements
    PASSWORD_MIN_LENGTH: int = 8
    PASSWORD_REQUIRE_UPPERCASE: bool = True
    PASSWORD_REQUIRE_LOWERCASE: bool = True
    PASSWORD_REQUIRE_DIGIT: bool = True
    PASSWORD_REQUIRE_SPECIAL: bool = True
    
    # Rate limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_PERIOD: int = 60
    
    # CORS
    CORS_ORIGINS: list = ["http://localhost:3000"]
    
    class Config:
        env_file = ".env"
        case_sensitive = True
```

### 7. Security Headers

```python
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    
    # Prevent clickjacking
    response.headers["X-Frame-Options"] = "DENY"
    
    # Prevent MIME sniffing
    response.headers["X-Content-Type-Options"] = "nosniff"
    
    # Enable XSS protection
    response.headers["X-XSS-Protection"] = "1; mode=block"
    
    # Content Security Policy
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    
    # HSTS
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    
    return response
```

## Vulnerability Reporting

### Reporting Process

1. **Do not** disclose vulnerability publicly
2. Email security@yourdomain.com with details
3. Include:
   - Description of vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)
4. Wait for acknowledgment (within 48 hours)
5. Allow time for fix (typically 30-90 days)
6. Coordinate disclosure timing

### Bug Bounty Program

We offer rewards for security vulnerabilities:

| Severity | Reward |
|----------|--------|
| Critical | $1000-$5000 |
| High | $500-$1000 |
| Medium | $100-$500 |
| Low | $50-$100 |

### Security Contact

- **Email**: security@yourdomain.com
- **PGP Key**: [Download](https://yourdomain.com/pgp-key.asc)
- **Response Time**: 48 hours

## Security Checklist

- [ ] Use HTTPS/TLS in production
- [ ] Implement JWT authentication
- [ ] Enable rate limiting
- [ ] Use parameterized queries
- [ ] Validate all inputs
- [ ] Hash passwords with bcrypt
- [ ] Store secrets securely
- [ ] Enable CORS properly
- [ ] Add security headers
- [ ] Implement audit logging
- [ ] Keep dependencies updated
- [ ] Use strong passwords
- [ ] Enable firewall
- [ ] Encrypt backups
- [ ] Regular security audits
- [ ] Monitor for suspicious activity
- [ ] Have incident response plan
- [ ] Train team on security

## Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [OWASP API Security](https://owasp.org/www-project-api-security/)
- [JWT Best Practices](https://tools.ietf.org/html/rfc8725)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [Docker Security](https://docs.docker.com/engine/security/)
