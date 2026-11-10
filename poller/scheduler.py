import asyncio
import config
from collectors.prometheus_client import PrometheusClient
from collectors.k3s_client import get_pods
from rules.evaluator import evaluate_container_states, evaluate_containers, evaluate_node, evaluate_pods
from logs_fetch.docker_logs import get_container_logs, get_container_states
from logs_fetch.k3s_logs import get_pod_logs
from llm.client import diagnose, diagnose_batch
from db.session import SessionLocal
from db import crud
from bot.formatter import alert_embed, batch_alert_embed, info_embed
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
            alert = await crud.get_open_alert(session, b["target"], b["alert_type"])
            fallback = "Alert detected. AI diagnosis is pending."
            delivered = await post_embed(alert_embed(b["target"], b["alert_type"], b["value"], fallback))
            if delivered:
                await crud.mark_diagnosed(session, alert, fallback)
                try:
                    alert_text = f"{b['alert_type']} on {b['target']}: value={b['value']}"
                    diagnosis = await diagnose(alert_text, logs_by_target[b["target"]])
                    await post_embed(info_embed(f"AI diagnosis: {b['target']}", diagnosis))
                    await crud.mark_diagnosed(session, alert, diagnosis)
                except Exception as error:
                    print(f"AI diagnosis failed after alert delivery: {type(error).__name__}: {error}", flush=True)
        else:
            fallback = "Alerts detected. AI diagnosis is pending."
            delivered = await post_embed(batch_alert_embed(ready, fallback))
            for b in ready:
                alert = await crud.get_open_alert(session, b["target"], b["alert_type"])
                if delivered:
                    await crud.mark_diagnosed(session, alert, fallback)
            if delivered:
                try:
                    diagnosis = await diagnose_batch(ready, logs_by_target)
                    await post_embed(info_embed("AI alert diagnosis", diagnosis))
                except Exception as error:
                    print(f"AI batch diagnosis failed after alert delivery: {type(error).__name__}: {error}", flush=True)


async def poll_once():
    cpu = await prom.container_cpu_percent()
    mem = await prom.container_mem_percent()
    node_cpu = await prom.node_cpu_percent()
    node_mem = await prom.node_mem_percent()
    node_disk = await prom.node_disk_percent()
    pods = await get_pods(namespace=config.K3S_NAMESPACE)
    containers = await get_container_states()
    await _resolve_recovered_containers(containers)

    breaches = (
        evaluate_containers(cpu, mem)
        + evaluate_container_states(containers)
        + evaluate_node(node_cpu, node_mem, node_disk)
        + evaluate_pods(pods)
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
