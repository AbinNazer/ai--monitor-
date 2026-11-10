import asyncio
import json


async def _run_kubectl(*args: str) -> str:
    proc = await asyncio.create_subprocess_exec(
        "kubectl", *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"kubectl {' '.join(args)} failed: {stderr.decode()}")
    return stdout.decode()


async def get_pods(namespace: str = "default") -> list[dict]:
    raw = await _run_kubectl("get", "pods", "-n", namespace, "-o", "json")
    data = json.loads(raw)
    pods = []
    for item in data.get("items", []):
        name = item["metadata"]["name"]
        phase = item["status"].get("phase", "Unknown")
        container_statuses = item["status"].get("containerStatuses", [])
        restarts = sum(cs.get("restartCount", 0) for cs in container_statuses)
        waiting_reason = None
        for cs in container_statuses:
            waiting = cs.get("state", {}).get("waiting")
            if waiting:
                waiting_reason = waiting.get("reason")
        pods.append({
            "name": name,
            "phase": phase,
            "restarts": restarts,
            "waiting_reason": waiting_reason,
        })
    return pods


async def describe_pod(name: str, namespace: str = "default") -> str:
    return await _run_kubectl("describe", "pod", name, "-n", namespace)


async def list_nodes() -> str:
    return await _run_kubectl("get", "nodes", "-o", "wide")