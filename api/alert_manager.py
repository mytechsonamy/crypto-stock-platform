"""
Alert Manager System
Handles alert creation, checking, and notification delivery
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any
import asyncio
import aiohttp
from loguru import logger

from storage.timescale_manager import TimescaleManager
from storage.redis_cache import RedisCacheManager
from monitoring.metrics import (
    alerts_triggered_total,
    alert_check_duration,
    notifications_sent_total,
    notification_failures_total
)


class AlertCondition(str, Enum):
    """Alert condition types"""
    PRICE_ABOVE = "price_above"
    PRICE_BELOW = "price_below"
    RSI_ABOVE = "rsi_above"
    RSI_BELOW = "rsi_below"
    MACD_CROSSOVER = "macd_crossover"
    VOLUME_SPIKE = "volume_spike"


class NotificationChannel(str, Enum):
    """Notification delivery channels"""
    WEBSOCKET = "websocket"
    EMAIL = "email"
    WEBHOOK = "webhook"
    SLACK = "slack"


@dataclass
class Alert:
    """Alert configuration"""
    alert_id: str
    user_id: str
    symbol: str
    condition: AlertCondition
    threshold: float
    channels: List[NotificationChannel]
    cooldown_seconds: int = 300  # 5 minutes default
    one_time: bool = False
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_triggered_at: Optional[datetime] = None
    trigger_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class AlertManager:
    """
    Manages alert lifecycle: creation, checking, and notification delivery
    """
    
    def __init__(
        self,
        db_manager: TimescaleManager,
        redis_manager: RedisCacheManager,
        smtp_config: Optional[Dict[str, str]] = None,
        slack_webhook_url: Optional[str] = None
    ):
        self.db = db_manager
        self.redis = redis_manager
        self.smtp_config = smtp_config or {}
        self.slack_webhook_url = slack_webhook_url
        
        # Cache for active alerts per symbol
        self._alerts_cache: Dict[str, List[Alert]] = {}
        self._cache_ttl = 300  # 5 minutes
        self._last_cache_refresh = datetime.utcnow()
        
        logger.info("AlertManager initialized")
    
    async def check_alerts(
        self,
        symbol: str,
        price: float,
        indicators: Dict[str, float]
    ) -> List[Alert]:
        """
        Check all active alerts for a symbol and trigger notifications
        
        Args:
            symbol: Trading symbol
            price: Current price
            indicators: Dictionary of indicator values (rsi, macd, etc.)
        
        Returns:
            List of triggered alerts
        """
        start_time = datetime.utcnow()
        triggered_alerts = []
        
        try:
            # Get active alerts for symbol
            alerts = await self._get_active_alerts(symbol)
            
            for alert in alerts:
                # Check if alert should trigger
                if await self._should_trigger(alert, price, indicators):
                    # Send notifications
                    await self._send_notifications(alert, price, indicators)
                    
                    # Update alert state
                    await self._update_alert_state(alert)
                    
                    triggered_alerts.append(alert)
                    
                    # Increment metrics
                    alerts_triggered_total.labels(
                        symbol=symbol,
                        condition=alert.condition.value
                    ).inc()
                    
                    logger.info(
                        f"Alert triggered: {alert.alert_id} for {symbol} "
                        f"(condition: {alert.condition.value}, threshold: {alert.threshold})"
                    )
            
            # Record check duration
            duration = (datetime.utcnow() - start_time).total_seconds()
            alert_check_duration.labels(symbol=symbol).observe(duration)
            
        except Exception as e:
            logger.error(f"Error checking alerts for {symbol}: {e}")
        
        return triggered_alerts
    
    async def _should_trigger(
        self,
        alert: Alert,
        price: float,
        indicators: Dict[str, float]
    ) -> bool:
        """
        Check if alert condition is met
        
        Args:
            alert: Alert configuration
            price: Current price
            indicators: Indicator values
        
        Returns:
            True if alert should trigger
        """
        # Check if alert is active
        if not alert.is_active:
            return False
        
        # Check cooldown period
        if alert.last_triggered_at:
            cooldown_end = alert.last_triggered_at + timedelta(seconds=alert.cooldown_seconds)
            if datetime.utcnow() < cooldown_end:
                return False
        
        # Check if one-time alert already triggered
        if alert.one_time and alert.trigger_count > 0:
            return False
        
        # Check condition
        condition_met = False
        
        if alert.condition == AlertCondition.PRICE_ABOVE:
            condition_met = price > alert.threshold
        
        elif alert.condition == AlertCondition.PRICE_BELOW:
            condition_met = price < alert.threshold
        
        elif alert.condition == AlertCondition.RSI_ABOVE:
            rsi = indicators.get('rsi')
            if rsi is not None:
                condition_met = rsi > alert.threshold
        
        elif alert.condition == AlertCondition.RSI_BELOW:
            rsi = indicators.get('rsi')
            if rsi is not None:
                condition_met = rsi < alert.threshold
        
        elif alert.condition == AlertCondition.MACD_CROSSOVER:
            macd = indicators.get('macd')
            macd_signal = indicators.get('macd_signal')
            if macd is not None and macd_signal is not None:
                # Check for bullish crossover (MACD crosses above signal)
                # Need previous values to detect crossover
                prev_macd = alert.metadata.get('prev_macd')
                prev_signal = alert.metadata.get('prev_signal')
                
                if prev_macd is not None and prev_signal is not None:
                    if alert.threshold > 0:  # Bullish crossover
                        condition_met = (prev_macd <= prev_signal) and (macd > macd_signal)
                    else:  # Bearish crossover
                        condition_met = (prev_macd >= prev_signal) and (macd < macd_signal)
                
                # Store current values for next check
                alert.metadata['prev_macd'] = macd
                alert.metadata['prev_signal'] = macd_signal
        
        elif alert.condition == AlertCondition.VOLUME_SPIKE:
            volume = indicators.get('volume')
            volume_sma = indicators.get('volume_sma')
            if volume is not None and volume_sma is not None:
                # Volume spike if current volume > threshold * average volume
                condition_met = volume > (alert.threshold * volume_sma)
        
        return condition_met
    
    async def _send_notifications(
        self,
        alert: Alert,
        price: float,
        indicators: Dict[str, float]
    ):
        """
        Send notifications through configured channels
        
        Args:
            alert: Alert configuration
            price: Current price
            indicators: Indicator values
        """
        # Prepare notification message
        message = self._format_notification_message(alert, price, indicators)
        
        # Send through each channel
        tasks = []
        for channel in alert.channels:
            if channel == NotificationChannel.WEBSOCKET:
                tasks.append(self._send_websocket_notification(alert, message))
            elif channel == NotificationChannel.EMAIL:
                tasks.append(self._send_email_notification(alert, message))
            elif channel == NotificationChannel.WEBHOOK:
                tasks.append(self._send_webhook_notification(alert, message))
            elif channel == NotificationChannel.SLACK:
                tasks.append(self._send_slack_notification(alert, message))
        
        # Send all notifications concurrently
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Log any failures
            for channel, result in zip(alert.channels, results):
                if isinstance(result, Exception):
                    logger.error(
                        f"Failed to send {channel.value} notification "
                        f"for alert {alert.alert_id}: {result}"
                    )
                    notification_failures_total.labels(
                        channel=channel.value,
                        alert_id=alert.alert_id
                    ).inc()
                else:
                    notifications_sent_total.labels(
                        channel=channel.value,
                        alert_id=alert.alert_id
                    ).inc()
    
    def _format_notification_message(
        self,
        alert: Alert,
        price: float,
        indicators: Dict[str, float]
    ) -> Dict[str, Any]:
        """Format notification message with alert details"""
        return {
            "alert_id": alert.alert_id,
            "symbol": alert.symbol,
            "condition": alert.condition.value,
            "threshold": alert.threshold,
            "current_price": price,
            "indicators": indicators,
            "timestamp": datetime.utcnow().isoformat(),
            "message": self._get_human_readable_message(alert, price, indicators)
        }
    
    def _get_human_readable_message(
        self,
        alert: Alert,
        price: float,
        indicators: Dict[str, float]
    ) -> str:
        """Generate human-readable alert message"""
        if alert.condition == AlertCondition.PRICE_ABOVE:
            return f"🚀 {alert.symbol} price ${price:.2f} is above ${alert.threshold:.2f}"
        
        elif alert.condition == AlertCondition.PRICE_BELOW:
            return f"📉 {alert.symbol} price ${price:.2f} is below ${alert.threshold:.2f}"
        
        elif alert.condition == AlertCondition.RSI_ABOVE:
            rsi = indicators.get('rsi', 0)
            return f"📈 {alert.symbol} RSI {rsi:.2f} is above {alert.threshold:.2f} (overbought)"
        
        elif alert.condition == AlertCondition.RSI_BELOW:
            rsi = indicators.get('rsi', 0)
            return f"📉 {alert.symbol} RSI {rsi:.2f} is below {alert.threshold:.2f} (oversold)"
        
        elif alert.condition == AlertCondition.MACD_CROSSOVER:
            direction = "bullish" if alert.threshold > 0 else "bearish"
            return f"🔄 {alert.symbol} MACD {direction} crossover detected"
        
        elif alert.condition == AlertCondition.VOLUME_SPIKE:
            volume = indicators.get('volume', 0)
            return f"📊 {alert.symbol} volume spike detected: {volume:.0f}"
        
        return f"Alert triggered for {alert.symbol}"
    
    async def _send_websocket_notification(self, alert: Alert, message: Dict[str, Any]):
        """Send notification via WebSocket (Redis pub/sub)"""
        try:
            channel = f"alerts:{alert.user_id}"
            await self.redis.publish(channel, message)
            logger.debug(f"WebSocket notification sent for alert {alert.alert_id}")
        except Exception as e:
            logger.error(f"Failed to send WebSocket notification: {e}")
            raise
    
    async def _send_email_notification(self, alert: Alert, message: Dict[str, Any]):
        """Send notification via email"""
        try:
            # TODO: Implement email sending using SMTP or service (SendGrid, AWS SES)
            # For now, just log
            logger.info(f"Email notification would be sent for alert {alert.alert_id}")
            logger.debug(f"Email content: {message['message']}")
            
            # Placeholder for actual implementation:
            # import aiosmtplib
            # from email.message import EmailMessage
            # 
            # msg = EmailMessage()
            # msg['Subject'] = f"Alert: {alert.symbol}"
            # msg['From'] = self.smtp_config.get('from_email')
            # msg['To'] = alert.metadata.get('email')
            # msg.set_content(message['message'])
            # 
            # await aiosmtplib.send(
            #     msg,
            #     hostname=self.smtp_config.get('host'),
            #     port=self.smtp_config.get('port'),
            #     username=self.smtp_config.get('username'),
            #     password=self.smtp_config.get('password'),
            #     use_tls=True
            # )
            
        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")
            raise
    
    async def _send_webhook_notification(self, alert: Alert, message: Dict[str, Any]):
        """Send notification via HTTP webhook"""
        try:
            webhook_url = alert.metadata.get('webhook_url')
            if not webhook_url:
                logger.warning(f"No webhook URL configured for alert {alert.alert_id}")
                return
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    webhook_url,
                    json=message,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status >= 400:
                        raise Exception(f"Webhook returned status {response.status}")
                    
                    logger.debug(f"Webhook notification sent for alert {alert.alert_id}")
        
        except Exception as e:
            logger.error(f"Failed to send webhook notification: {e}")
            raise
    
    async def _send_slack_notification(self, alert: Alert, message: Dict[str, Any]):
        """Send notification via Slack webhook"""
        try:
            slack_url = self.slack_webhook_url or alert.metadata.get('slack_webhook_url')
            if not slack_url:
                logger.warning(f"No Slack webhook URL configured for alert {alert.alert_id}")
                return
            
            # Format Slack message
            slack_message = {
                "text": message['message'],
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*{message['message']}*"
                        }
                    },
                    {
                        "type": "section",
                        "fields": [
                            {
                                "type": "mrkdwn",
                                "text": f"*Symbol:*\n{alert.symbol}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Price:*\n${message['current_price']:.2f}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Condition:*\n{alert.condition.value}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*Threshold:*\n{alert.threshold}"
                            }
                        ]
                    }
                ]
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    slack_url,
                    json=slack_message,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status >= 400:
                        raise Exception(f"Slack webhook returned status {response.status}")
                    
                    logger.debug(f"Slack notification sent for alert {alert.alert_id}")
        
        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")
            raise
    
    async def _update_alert_state(self, alert: Alert):
        """Update alert state after triggering"""
        alert.last_triggered_at = datetime.utcnow()
        alert.trigger_count += 1
        
        # Deactivate one-time alerts
        if alert.one_time:
            alert.is_active = False
        
        # Update in database
        await self.db.update_alert(alert)
        
        # Invalidate cache
        if alert.symbol in self._alerts_cache:
            del self._alerts_cache[alert.symbol]
    
    async def _get_active_alerts(self, symbol: str) -> List[Alert]:
        """Get active alerts for symbol (with caching)"""
        # Check cache
        if symbol in self._alerts_cache:
            cache_age = (datetime.utcnow() - self._last_cache_refresh).total_seconds()
            if cache_age < self._cache_ttl:
                return self._alerts_cache[symbol]
        
        # Fetch from database
        alerts = await self.db.get_active_alerts(symbol)
        
        # Update cache
        self._alerts_cache[symbol] = alerts
        self._last_cache_refresh = datetime.utcnow()
        
        return alerts
    
    async def create_alert(self, alert: Alert) -> Alert:
        """Create new alert"""
        await self.db.insert_alert(alert)
        
        # Invalidate cache
        if alert.symbol in self._alerts_cache:
            del self._alerts_cache[alert.symbol]
        
        logger.info(f"Alert created: {alert.alert_id} for {alert.symbol}")
        return alert
    
    async def update_alert(self, alert: Alert) -> Alert:
        """Update existing alert"""
        await self.db.update_alert(alert)
        
        # Invalidate cache
        if alert.symbol in self._alerts_cache:
            del self._alerts_cache[alert.symbol]
        
        logger.info(f"Alert updated: {alert.alert_id}")
        return alert
    
    async def delete_alert(self, alert_id: str, user_id: str):
        """Delete alert"""
        await self.db.delete_alert(alert_id, user_id)
        
        # Invalidate entire cache (we don't know which symbol)
        self._alerts_cache.clear()
        
        logger.info(f"Alert deleted: {alert_id}")
    
    async def get_user_alerts(self, user_id: str) -> List[Alert]:
        """Get all alerts for a user"""
        return await self.db.get_user_alerts(user_id)
    
    async def get_alert(self, alert_id: str, user_id: str) -> Optional[Alert]:
        """Get specific alert"""
        return await self.db.get_alert(alert_id, user_id)
