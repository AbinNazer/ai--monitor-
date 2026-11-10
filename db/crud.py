from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import Alert, ContainerState, PodState


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


async def get_container_states(session: AsyncSession):
    result = await session.execute(select(ContainerState))
    return {item.name: item for item in result.scalars()}


async def touch_container_state(session, name, status, exit_code, now):
    state = await session.get(ContainerState, name)
    if state is None:
        state = ContainerState(name=name)
        session.add(state)
    state.last_status = status
    state.last_exit_code = exit_code
    if status == "running":
        state.last_seen_running = now
        state.missing_since = None
    elif state.missing_since is None:
        state.missing_since = now
    await session.flush()
    return state


async def mark_container_missing(session, name, now):
    state = await session.get(ContainerState, name)
    if state and state.missing_since is None:
        state.missing_since = now
        await session.flush()


async def get_pod_states(session):
    result = await session.execute(select(PodState))
    return {item.name: item for item in result.scalars()}


async def touch_pod_state(session, key, namespace, phase, waiting_reason, restarts, bad, now):
    state = await session.get(PodState, key)
    if state is None:
        state = PodState(name=key, namespace=namespace)
        session.add(state)
    state.last_phase = phase
    state.last_waiting_reason = waiting_reason
    state.last_restarts = restarts
    state.bad_since = now if bad and state.bad_since is None else (state.bad_since if bad else None)
    await session.flush()
    return state


async def reset_alert(session, target, alert_type):
    alert = await get_open_alert(session, target, alert_type)
    if alert:
        alert.breach_count = 0
        alert.notified = False
        alert.diagnosis = None
        alert.raw_metrics = {}
        await session.flush()
