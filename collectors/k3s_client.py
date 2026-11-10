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


async def get_pods(namespace: str = "all") -> list[dict]:
    scope = ["--all-namespaces"] if namespace in ("all", "*") else ["-n", namespace]
    raw = await _run_kubectl("get", "pods", *scope, "-o", "json")
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
            "namespace": item["metadata"].get("namespace", "default"),
            "phase": phase,
            "restarts": restarts,
            "waiting_reason": waiting_reason,
        })
    return pods


async def describe_pod(name: str, namespace: str = "default") -> str:
    return await _run_kubectl("describe", "pod", name, "-n", namespace)


async def get_pod_ports(name: str, namespace: str = "default") -> str:
    raw = await _run_kubectl("get", "pod", name, "-n", namespace, "-o", "json")
    data = json.loads(raw)
    ports = []
    for container in data.get("spec", {}).get("containers", []):
        for port in container.get("ports", []):
            value = f"{container.get('name', 'container')}: {port.get('containerPort')}"
            if port.get("protocol"):
                value += f"/{port['protocol']}"
            ports.append(value)
    return "\n".join(ports) or f"`{namespace}/{name}` has no declared container ports."


async def list_nodes() -> str:
    return await _run_kubectl("get", "nodes", "-o", "wide")
