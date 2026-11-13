import asyncio
from datetime import datetime, timezone
import config
from collectors.prometheus_client import PrometheusClient
from collectors.k3s_client import get_pods
from collectors.docker_stats import get_container_stats
from rules.evaluator import evaluate_container_states, evaluate_containers, evaluate_node, evaluate_pod_states
from logs_fetch.docker_logs import get_container_logs, get_container_states
from logs_fetch.k3s_logs import get_pod_logs
from llm.client import diagnose, diagnose_batch
from db.session import SessionLocal
from db import crud
from rules import thresholds
from bot.formatter import alert_embed, batch_alert_embed
from bot.client import post_embed

prom = PrometheusClient()


async def _fetch_logs(target: str, alert_type: str) -> str:
    if alert_type.startswith("pod_"):
        return await get_pod_logs(target)
    if alert_type.startswith("node_"):
        return ""  # no single container to pull logs from
    return await get_container_logs(target)


async def _ready_breaches(breaches: list[dict]) -> list[dict]:
    """Bump breach counters in DB, return only the ones that just crossed
    the sustained-breach threshold and haven't been notified yet."""
    ready = []
    async with SessionLocal() as session:
        for b in breaches:
            alert = await crud.create_or_bump_alert(
                session, b["target"], b["alert_type"], {"value": str(b["value"])}
            )
            if alert.breach_count >= config.BREACH_THRESHOLD_COUNT and not alert.notified:
                ready.append(b)
    return ready


async def _resolve_recovered_containers(containers: list[dict]):
    async with SessionLocal() as session:
        for container in containers:
            if container["running"]:
                await crud.resolve_alert(session, container["name"], "container_down")


async def _dispatch(ready: list[dict]):
    if not ready:
        return

    logs_by_target = {}
    for b in ready:
        logs_by_target[b["target"]] = await _fetch_logs(b["target"], b["alert_type"])

    async with SessionLocal() as session:
        if len(ready) == 1:
            b = ready[0]
            alert_text = f"{b['alert_type']} on {b['target']}: value={b['value']}"
            diagnosis = await diagnose(alert_text, logs_by_target[b["target"]])
            alert = await crud.get_open_alert(session, b["target"], b["alert_type"])
            delivered = await post_embed(alert_embed(b["target"], b["alert_type"], b["value"], diagnosis))
            if delivered:
                await crud.mark_diagnosed(session, alert, diagnosis)
        else:
            diagnosis = await diagnose_batch(ready, logs_by_target)
            delivered = await post_embed(batch_alert_embed(ready, diagnosis))
            for b in ready:
                alert = await crud.get_open_alert(session, b["target"], b["alert_type"])
                if delivered:
                    await crud.mark_diagnosed(session, alert, diagnosis)


async def poll_once():
    container_stats = await get_container_stats()
    node_cpu = await prom.node_cpu_percent()
    node_mem = await prom.node_mem_percent()
    node_disk = await prom.node_disk_percent()
    pods = await get_pods(namespace=config.K3S_NAMESPACE)
    containers = await get_container_states()
    now = datetime.now(timezone.utc)
    async with SessionLocal() as session:
        container_states = await crud.get_container_states(session)
        current_names = {item["name"] for item in containers}
        for item in containers:
            state = await crud.touch_container_state(
                session, item["name"], item["state"], item["exit_code"], now
            )
            if item["running"]:
                await crud.reset_alert(session, item["name"], "container_down")
        for name in set(container_states) - current_names:
            await crud.mark_container_missing(session, name, now)

        pod_states = await crud.get_pod_states(session)
        for pod in pods:
            key = f"{pod['namespace']}/{pod['name']}"
            bad = pod["waiting_reason"] in thresholds.POD_CRASHLOOP_REASONS
            bad = bad or pod["restarts"] >= thresholds.POD_RESTART_THRESHOLD
            await crud.touch_pod_state(
                session, key, pod["namespace"], pod["phase"],
                pod["waiting_reason"], pod["restarts"], bad, now,
            )
            if not bad:
                await crud.reset_alert(session, key, "pod_crashloop")
                await crud.reset_alert(session, key, "pod_restart_high")
        await session.commit()

    breaches = (
        evaluate_containers(container_stats)
        + evaluate_container_states(containers, container_states, now, config.DEPLOY_GRACE_SECONDS)
        + evaluate_node(node_cpu, node_mem, node_disk)
        + evaluate_pod_states(pods, pod_states, now, config.DEPLOY_GRACE_SECONDS)
    )

    ready = await _ready_breaches(breaches)
    await _dispatch(ready)


async def run_forever():
    while True:
        try:
            await poll_once()
        except Exception as e:
            print(f"poll error: {type(e).__name__}: {e}", flush=True)
        await asyncio.sleep(config.POLL_INTERVAL_SECONDS)
