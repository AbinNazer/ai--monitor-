from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import Alert


async def get_open_alert(session: AsyncSession, target: str, alert_type: str) -> Alert | None:
    result = await session.execute(
        select(Alert).where(
            Alert.target == target,
            Alert.alert_type == alert_type,
            Alert.status == "open",
        )
    )
    return result.scalar_one_or_none()


async def create_or_bump_alert(session: AsyncSession, target: str, alert_type: str, raw_metrics: dict) -> Alert:
    alert = await get_open_alert(session, target, alert_type)
    if alert:
        alert.breach_count += 1
        alert.raw_metrics = raw_metrics
    else:
        alert = Alert(target=target, alert_type=alert_type, raw_metrics=raw_metrics, breach_count=1)
        session.add(alert)
    await session.commit()
    await session.refresh(alert)
    return alert


async def mark_diagnosed(session: AsyncSession, alert: Alert, diagnosis: str):
    alert.diagnosis = diagnosis
    alert.notified = True
    await session.commit()


async def resolve_alert(session: AsyncSession, target: str, alert_type: str):
    alert = await get_open_alert(session, target, alert_type)
    if alert:
        alert.status = "resolved"
        from datetime import datetime, timezone
        alert.resolved_at = datetime.now(timezone.utc)
        await session.commit()