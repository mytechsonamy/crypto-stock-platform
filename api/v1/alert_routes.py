"""
Alert API Routes
CRUD operations for user alerts
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
import uuid

from api.auth import get_current_user
from api.alert_manager import Alert, AlertCondition, NotificationChannel, AlertManager
from storage.timescale_manager import TimescaleManager
from storage.redis_cache import RedisCacheManager
from loguru import logger


router = APIRouter(prefix="/alerts", tags=["alerts"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class AlertCreate(BaseModel):
    """Request model for creating an alert"""
    symbol: str = Field(..., description="Trading symbol to monitor")
    condition: AlertCondition = Field(..., description="Alert condition type")
    threshold: float = Field(..., ge=0, description="Threshold value")
    channels: List[NotificationChannel] = Field(..., description="Notification channels")
    cooldown_seconds: int = Field(300, ge=0, description="Cooldown period in seconds")
    one_time: bool = Field(False, description="Trigger only once")
    metadata: Optional[dict] = Field(default_factory=dict, description="Additional configuration")
    
    class Config:
        schema_extra = {
            "example": {
                "symbol": "BTCUSDT",
                "condition": "price_above",
                "threshold": 50000.0,
                "channels": ["websocket", "email"],
                "cooldown_seconds": 300,
                "one_time": False,
                "metadata": {
                    "email": "user@example.com",
                    "webhook_url": "https://example.com/webhook"
                }
            }
        }


class AlertUpdate(BaseModel):
    """Request model for updating an alert"""
    condition: Optional[AlertCondition] = None
    threshold: Optional[float] = Field(None, ge=0)
    channels: Optional[List[NotificationChannel]] = None
    cooldown_seconds: Optional[int] = Field(None, ge=0)
    one_time: Optional[bool] = None
    is_active: Optional[bool] = None
    metadata: Optional[dict] = None


class AlertResponse(BaseModel):
    """Response model for alert"""
    alert_id: str
    user_id: str
    symbol: str
    condition: str
    threshold: float
    channels: List[str]
    cooldown_seconds: int
    one_time: bool
    is_active: bool
    created_at: datetime
    last_triggered_at: Optional[datetime]
    trigger_count: int
    metadata: dict
    
    class Config:
        schema_extra = {
            "example": {
                "alert_id": "123e4567-e89b-12d3-a456-426614174000",
                "user_id": "user123",
                "symbol": "BTCUSDT",
                "condition": "price_above",
                "threshold": 50000.0,
                "channels": ["websocket", "email"],
                "cooldown_seconds": 300,
                "one_time": False,
                "is_active": True,
                "created_at": "2024-01-01T00:00:00Z",
                "last_triggered_at": None,
                "trigger_count": 0,
                "metadata": {"email": "user@example.com"}
            }
        }


# ============================================================================
# DEPENDENCY INJECTION
# ============================================================================

async def get_alert_manager() -> AlertManager:
    """Get AlertManager instance"""
    # This should be injected from main.py app state
    # For now, we'll create a placeholder
    from api.main import app
    return app.state.alert_manager


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post(
    "",
    response_model=AlertResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new alert",
    description="Create a new alert for price or indicator conditions"
)
async def create_alert(
    alert_data: AlertCreate,
    current_user: dict = Depends(get_current_user),
    alert_manager: AlertManager = Depends(get_alert_manager)
):
    """
    Create a new alert.
    
    - **symbol**: Trading symbol to monitor
    - **condition**: Alert condition (price_above, price_below, rsi_above, etc.)
    - **threshold**: Threshold value for the condition
    - **channels**: Notification channels (websocket, email, webhook, slack)
    - **cooldown_seconds**: Minimum time between notifications (default: 300)
    - **one_time**: If true, alert triggers only once (default: false)
    - **metadata**: Additional configuration (email, webhook_url, etc.)
    """
    try:
        # Create alert object
        alert = Alert(
            alert_id=str(uuid.uuid4()),
            user_id=current_user['user_id'],
            symbol=alert_data.symbol.upper(),
            condition=alert_data.condition,
            threshold=alert_data.threshold,
            channels=alert_data.channels,
            cooldown_seconds=alert_data.cooldown_seconds,
            one_time=alert_data.one_time,
            is_active=True,
            metadata=alert_data.metadata or {}
        )
        
        # Save to database
        await alert_manager.create_alert(alert)
        
        logger.info(
            f"Alert created: {alert.alert_id} by user {current_user['user_id']} "
            f"for {alert.symbol}"
        )
        
        # Convert to response model
        return AlertResponse(
            alert_id=alert.alert_id,
            user_id=alert.user_id,
            symbol=alert.symbol,
            condition=alert.condition.value,
            threshold=alert.threshold,
            channels=[ch.value for ch in alert.channels],
            cooldown_seconds=alert.cooldown_seconds,
            one_time=alert.one_time,
            is_active=alert.is_active,
            created_at=alert.created_at,
            last_triggered_at=alert.last_triggered_at,
            trigger_count=alert.trigger_count,
            metadata=alert.metadata
        )
        
    except Exception as e:
        logger.error(f"Error creating alert: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create alert: {str(e)}"
        )


@router.get(
    "",
    response_model=List[AlertResponse],
    summary="List user alerts",
    description="Get all alerts for the authenticated user"
)
async def list_alerts(
    current_user: dict = Depends(get_current_user),
    alert_manager: AlertManager = Depends(get_alert_manager)
):
    """
    Get all alerts for the authenticated user.
    
    Returns a list of all alerts (active and inactive) created by the user.
    """
    try:
        alerts = await alert_manager.get_user_alerts(current_user['user_id'])
        
        return [
            AlertResponse(
                alert_id=alert.alert_id,
                user_id=alert.user_id,
                symbol=alert.symbol,
                condition=alert.condition.value,
                threshold=alert.threshold,
                channels=[ch.value for ch in alert.channels],
                cooldown_seconds=alert.cooldown_seconds,
                one_time=alert.one_time,
                is_active=alert.is_active,
                created_at=alert.created_at,
                last_triggered_at=alert.last_triggered_at,
                trigger_count=alert.trigger_count,
                metadata=alert.metadata
            )
            for alert in alerts
        ]
        
    except Exception as e:
        logger.error(f"Error listing alerts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list alerts: {str(e)}"
        )


@router.get(
    "/{alert_id}",
    response_model=AlertResponse,
    summary="Get alert details",
    description="Get details of a specific alert"
)
async def get_alert(
    alert_id: str,
    current_user: dict = Depends(get_current_user),
    alert_manager: AlertManager = Depends(get_alert_manager)
):
    """
    Get details of a specific alert.
    
    - **alert_id**: UUID of the alert
    
    Returns alert details if the user owns the alert.
    """
    try:
        alert = await alert_manager.get_alert(alert_id, current_user['user_id'])
        
        if not alert:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Alert not found"
            )
        
        return AlertResponse(
            alert_id=alert.alert_id,
            user_id=alert.user_id,
            symbol=alert.symbol,
            condition=alert.condition.value,
            threshold=alert.threshold,
            channels=[ch.value for ch in alert.channels],
            cooldown_seconds=alert.cooldown_seconds,
            one_time=alert.one_time,
            is_active=alert.is_active,
            created_at=alert.created_at,
            last_triggered_at=alert.last_triggered_at,
            trigger_count=alert.trigger_count,
            metadata=alert.metadata
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting alert: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get alert: {str(e)}"
        )


@router.put(
    "/{alert_id}",
    response_model=AlertResponse,
    summary="Update alert",
    description="Update an existing alert"
)
async def update_alert(
    alert_id: str,
    alert_data: AlertUpdate,
    current_user: dict = Depends(get_current_user),
    alert_manager: AlertManager = Depends(get_alert_manager)
):
    """
    Update an existing alert.
    
    - **alert_id**: UUID of the alert
    - Only provided fields will be updated
    
    Returns updated alert details.
    """
    try:
        # Get existing alert
        alert = await alert_manager.get_alert(alert_id, current_user['user_id'])
        
        if not alert:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Alert not found"
            )
        
        # Update fields
        if alert_data.condition is not None:
            alert.condition = alert_data.condition
        if alert_data.threshold is not None:
            alert.threshold = alert_data.threshold
        if alert_data.channels is not None:
            alert.channels = alert_data.channels
        if alert_data.cooldown_seconds is not None:
            alert.cooldown_seconds = alert_data.cooldown_seconds
        if alert_data.one_time is not None:
            alert.one_time = alert_data.one_time
        if alert_data.is_active is not None:
            alert.is_active = alert_data.is_active
        if alert_data.metadata is not None:
            alert.metadata.update(alert_data.metadata)
        
        # Save to database
        await alert_manager.update_alert(alert)
        
        logger.info(f"Alert updated: {alert_id} by user {current_user['user_id']}")
        
        return AlertResponse(
            alert_id=alert.alert_id,
            user_id=alert.user_id,
            symbol=alert.symbol,
            condition=alert.condition.value,
            threshold=alert.threshold,
            channels=[ch.value for ch in alert.channels],
            cooldown_seconds=alert.cooldown_seconds,
            one_time=alert.one_time,
            is_active=alert.is_active,
            created_at=alert.created_at,
            last_triggered_at=alert.last_triggered_at,
            trigger_count=alert.trigger_count,
            metadata=alert.metadata
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating alert: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update alert: {str(e)}"
        )


@router.delete(
    "/{alert_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete alert",
    description="Delete an alert"
)
async def delete_alert(
    alert_id: str,
    current_user: dict = Depends(get_current_user),
    alert_manager: AlertManager = Depends(get_alert_manager)
):
    """
    Delete an alert.
    
    - **alert_id**: UUID of the alert
    
    Returns 204 No Content on success.
    """
    try:
        # Check if alert exists and user owns it
        alert = await alert_manager.get_alert(alert_id, current_user['user_id'])
        
        if not alert:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Alert not found"
            )
        
        # Delete alert
        await alert_manager.delete_alert(alert_id, current_user['user_id'])
        
        logger.info(f"Alert deleted: {alert_id} by user {current_user['user_id']}")
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting alert: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete alert: {str(e)}"
        )
