"""
Authentication & Authorization Manager.

Features:
- JWT token management
- Password hashing with bcrypt
- Role-based access control (RBAC)
- WebSocket authentication
- Token refresh mechanism
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, List
from fastapi import Depends, HTTPException, status, WebSocketException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from loguru import logger


# Configuration
SECRET_KEY = "your-secret-key-here-change-in-production"  # Should be in environment variables
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# HTTP Bearer token scheme
security = HTTPBearer()


# ==================== MODELS ====================

class Token(BaseModel):
    """Token response model."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenData(BaseModel):
    """Token payload data."""
    user_id: Optional[str] = None
    username: Optional[str] = None
    roles: List[str] = []
    exp: Optional[datetime] = None


class User(BaseModel):
    """User model."""
    user_id: str
    username: str
    email: Optional[str] = None
    roles: List[str] = []
    is_active: bool = True


class UserInDB(User):
    """User model with hashed password."""
    hashed_password: str


class LoginRequest(BaseModel):
    """Login request model."""
    username: str
    password: str


class RegisterRequest(BaseModel):
    """Register request model."""
    username: str
    email: str
    password: str


# ==================== AUTH MANAGER ====================

class AuthManager:
    """
    Authentication and authorization manager.
    
    Features:
    - JWT token creation and verification
    - Password hashing and verification
    - Role-based access control
    - WebSocket authentication
    """
    
    def __init__(
        self,
        secret_key: str = SECRET_KEY,
        algorithm: str = ALGORITHM,
        access_token_expire_minutes: int = ACCESS_TOKEN_EXPIRE_MINUTES
    ):
        """
        Initialize auth manager.
        
        Args:
            secret_key: Secret key for JWT signing
            algorithm: JWT algorithm
            access_token_expire_minutes: Token expiration time
        """
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.access_token_expire_minutes = access_token_expire_minutes
        
        logger.info(
            f"AuthManager initialized: "
            f"algorithm={algorithm}, "
            f"token_expiry={access_token_expire_minutes}min"
        )
    
    # ==================== TOKEN MANAGEMENT ====================
    
    def create_access_token(
        self,
        data: Dict,
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Create JWT access token.
        
        Args:
            data: Token payload data
            expires_delta: Optional custom expiration time
            
        Returns:
            Encoded JWT token
        """
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        
        to_encode.update({"exp": expire})
        
        encoded_jwt = jwt.encode(
            to_encode,
            self.secret_key,
            algorithm=self.algorithm
        )
        
        logger.debug(f"Created access token for user: {data.get('sub')}")
        
        return encoded_jwt
    
    def create_refresh_token(
        self,
        data: Dict,
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Create JWT refresh token.
        
        Args:
            data: Token payload data
            expires_delta: Optional custom expiration time
            
        Returns:
            Encoded JWT refresh token
        """
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        
        to_encode.update({"exp": expire, "type": "refresh"})
        
        encoded_jwt = jwt.encode(
            to_encode,
            self.secret_key,
            algorithm=self.algorithm
        )
        
        logger.debug(f"Created refresh token for user: {data.get('sub')}")
        
        return encoded_jwt
    
    def verify_token(self, token: str) -> TokenData:
        """
        Verify and decode JWT token.
        
        Args:
            token: JWT token string
            
        Returns:
            TokenData with decoded payload
            
        Raises:
            HTTPException: If token is invalid or expired
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )
            
            user_id: str = payload.get("sub")
            username: str = payload.get("username")
            roles: List[str] = payload.get("roles", [])
            exp: datetime = datetime.fromtimestamp(payload.get("exp"))
            
            if user_id is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token: missing user_id",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            token_data = TokenData(
                user_id=user_id,
                username=username,
                roles=roles,
                exp=exp
            )
            
            return token_data
            
        except JWTError as e:
            logger.warning(f"Token verification failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    # ==================== PASSWORD MANAGEMENT ====================
    
    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash password using bcrypt.
        
        Args:
            password: Plain text password
            
        Returns:
            Hashed password
        """
        return pwd_context.hash(password)
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """
        Verify password against hash.
        
        Args:
            plain_password: Plain text password
            hashed_password: Hashed password
            
        Returns:
            True if password matches
        """
        return pwd_context.verify(plain_password, hashed_password)
    
    # ==================== USER MANAGEMENT ====================
    
    async def get_user(self, username: str) -> Optional[UserInDB]:
        """
        Get user from database.
        
        Args:
            username: Username
            
        Returns:
            User object or None
            
        Note: This is a placeholder. Implement actual database lookup.
        """
        # Placeholder - implement actual database lookup
        # For now, return a demo user
        if username == "demo":
            return UserInDB(
                user_id="1",
                username="demo",
                email="demo@example.com",
                roles=["user"],
                is_active=True,
                hashed_password=self.hash_password("demo123")
            )
        return None
    
    async def authenticate_user(
        self,
        username: str,
        password: str
    ) -> Optional[UserInDB]:
        """
        Authenticate user with username and password.
        
        Args:
            username: Username
            password: Plain text password
            
        Returns:
            User object if authenticated, None otherwise
        """
        user = await self.get_user(username)
        
        if not user:
            logger.warning(f"Authentication failed: user not found - {username}")
            return None
        
        if not self.verify_password(password, user.hashed_password):
            logger.warning(f"Authentication failed: invalid password - {username}")
            return None
        
        if not user.is_active:
            logger.warning(f"Authentication failed: user inactive - {username}")
            return None
        
        logger.info(f"User authenticated successfully: {username}")
        return user
    
    # ==================== DEPENDENCIES ====================
    
    async def get_current_user(
        self,
        credentials: HTTPAuthorizationCredentials = Depends(security)
    ) -> User:
        """
        Get current user from JWT token.
        
        Dependency for protected endpoints.
        
        Args:
            credentials: HTTP Bearer credentials
            
        Returns:
            Current user
            
        Raises:
            HTTPException: If authentication fails
        """
        token = credentials.credentials
        token_data = self.verify_token(token)
        
        user = await self.get_user(token_data.username)
        
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        return User(**user.dict())
    
    def check_permission(
        self,
        required_roles: List[str]
    ):
        """
        Check if user has required roles.
        
        Dependency for role-based access control.
        
        Args:
            required_roles: List of required roles
            
        Returns:
            Dependency function
        """
        async def permission_checker(
            current_user: User = Depends(self.get_current_user)
        ) -> User:
            """Check if user has required roles."""
            if not any(role in current_user.roles for role in required_roles):
                logger.warning(
                    f"Permission denied for user {current_user.username}: "
                    f"required {required_roles}, has {current_user.roles}"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions"
                )
            return current_user
        
        return permission_checker
    
    # ==================== WEBSOCKET AUTHENTICATION ====================
    
    async def authenticate_websocket(
        self,
        token: Optional[str] = None
    ) -> User:
        """
        Authenticate WebSocket connection.
        
        Args:
            token: JWT token from query parameter or header
            
        Returns:
            Authenticated user
            
        Raises:
            WebSocketException: If authentication fails (code 4001)
        """
        if not token:
            logger.warning("WebSocket authentication failed: no token provided")
            raise WebSocketException(
                code=4001,
                reason="Authentication required"
            )
        
        try:
            token_data = self.verify_token(token)
            user = await self.get_user(token_data.username)
            
            if user is None:
                raise WebSocketException(
                    code=4001,
                    reason="User not found"
                )
            
            logger.info(f"WebSocket authenticated: {user.username}")
            return User(**user.dict())
            
        except HTTPException:
            logger.warning("WebSocket authentication failed: invalid token")
            raise WebSocketException(
                code=4001,
                reason="Invalid or expired token"
            )
    
    # ==================== TOKEN REFRESH ====================
    
    async def refresh_access_token(self, refresh_token: str) -> Token:
        """
        Refresh access token using refresh token.
        
        Args:
            refresh_token: Valid refresh token
            
        Returns:
            New access token
            
        Raises:
            HTTPException: If refresh token is invalid
        """
        try:
            payload = jwt.decode(
                refresh_token,
                self.secret_key,
                algorithms=[self.algorithm]
            )
            
            # Check if it's a refresh token
            if payload.get("type") != "refresh":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token type"
                )
            
            user_id = payload.get("sub")
            username = payload.get("username")
            roles = payload.get("roles", [])
            
            # Create new access token
            access_token = self.create_access_token(
                data={
                    "sub": user_id,
                    "username": username,
                    "roles": roles
                }
            )
            
            logger.info(f"Access token refreshed for user: {username}")
            
            return Token(
                access_token=access_token,
                token_type="bearer",
                expires_in=self.access_token_expire_minutes * 60
            )
            
        except JWTError as e:
            logger.warning(f"Token refresh failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )


# Global auth manager instance
auth_manager = AuthManager()


# Convenience dependencies
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    """Get current user dependency."""
    return await auth_manager.get_current_user(credentials)


def require_roles(roles: List[str]):
    """Require specific roles dependency."""
    return auth_manager.check_permission(roles)
