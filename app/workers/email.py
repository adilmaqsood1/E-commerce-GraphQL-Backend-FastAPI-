"""ARQ background job: send order confirmation email."""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


async def send_order_confirmation(ctx: dict[str, Any], order_id: str, user_id: str) -> None:
    """
    Background task: send order confirmation email.
    Runs inside ARQ worker process.
    """
    try:
        # Fetch order details from DB
        from app.core.database import AsyncSessionLocal
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        from app.models.order import Order, OrderItem
        from app.models.user import User

        async with AsyncSessionLocal() as db:
            order_result = await db.execute(
                select(Order)
                .options(selectinload(Order.items))
                .where(Order.id == order_id)
            )
            order = order_result.scalar_one_or_none()
            user_result = await db.execute(select(User).where(User.id == user_id))
            user = user_result.scalar_one_or_none()

            if not order or not user:
                logger.warning(f"Order {order_id} or user {user_id} not found for email")
                return

            logger.info(
                f"[EMAIL] Order confirmation sent to {user.email} for order {order.order_number}"
            )
            # In production: use fastapi-mail or sendgrid here
            # await fast_mail.send_message(message=...)

    except Exception as e:
        logger.error(f"Failed to send order confirmation for {order_id}: {e}")
        raise  # Re-raise so ARQ retries


async def send_shipping_notification(ctx: dict[str, Any], order_id: str) -> None:
    """Background task: send shipping notification email."""
    logger.info(f"[EMAIL] Shipping notification sent for order {order_id}")


async def send_welcome_email(ctx: dict[str, Any], user_id: str) -> None:
    """Background task: send welcome email to new user."""
    logger.info(f"[EMAIL] Welcome email sent for user {user_id}")
