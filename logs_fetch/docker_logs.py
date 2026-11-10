import asyncio
import json
import re

ERROR_PATTERNS = re.compile(
    r"(error|exception|traceback|fatal|panic|failed|refused|timeout|crash)",
    re.IGNORECASE,
)


async def get_container_logs(name: str, tail: int = 50) -> str:
    proc = await asyncio.create_subprocess_exec(
        "docker", "logs", "--tail", str(tail), name,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    output = stdout.decode(errors="replace") + stderr.decode(errors="replace")
    return output[-4000:]  # cap size for LLM context


def summarize_logs(raw_logs: str, name: str, recent_count: int = 5) -> str:
    lines = [line.strip() for line in raw_logs.splitlines() if line.strip()]
    if not lines:
        return f"{name}: no log lines returned."
    error_lines = [line for line in lines if ERROR_PATTERNS.search(line)]
    parts = [f"{name}: fetched {len(lines)} log lines."]
    if error_lines:
        parts.append(f"\n**{len(error_lines)} error pattern(s) detected:**")
        parts.extend(f"- {line[:200]}" for line in error_lines[-5:])
    else:
        parts.append("No error patterns detected.")
    parts.append("\n**Recent lines:**")
    parts.extend(f"- {line[:200]}" for line in lines[-recent_count:])
    return "\n".join(parts)


async def get_container_error_logs(name: str, since: str = "24h") -> str:
    proc = await asyncio.create_subprocess_exec(
        "docker", "logs", "--since", since, "--timestamps", name,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        return (stdout + stderr).decode(errors="replace").strip()
    lines = stdout.decode(errors="replace").splitlines()
    pattern = re.compile(r"error|err\b|exception|traceback|fatal|critical|failed|failure", re.IGNORECASE)
    matches = [line for line in lines if pattern.search(line)]
    return "\n".join(matches)


async def list_containers() -> str:
    return await _list_containers(all_containers=False)


async def list_all_containers() -> str:
    return await _list_containers(all_containers=True)


async def get_container_states() -> list[dict]:
    proc = await asyncio.create_subprocess_exec(
        "docker", "ps", "-a", "--format", "{{json .}}",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(stderr.decode().strip() or "Unable to query Docker containers")
    states = []
    for line in stdout.decode(errors="replace").splitlines():
        item = json.loads(line)
        status = item.get("Status", "")
        state = item.get("State", "").lower()
        exit_code = item.get("ExitCode")
        states.append({"name": item.get("Names", "unknown"), "status": status,
                       "image": item.get("Image", "unknown"),
                       "ports": item.get("Ports", ""),
                       "state": state,
                       "exit_code": int(exit_code or 0),
                       "running": state == "running"})
    return states


async def get_container_ports(name: str) -> str:
    states = await get_container_states()
    container = next((item for item in states if item["name"] == name), None)
    if not container:
        return f"No container named `{name}` was found."
    return container["ports"] or f"`{name}` has no published ports."


async def _list_containers(all_containers: bool) -> str:
    args = ["docker", "ps"]
    if all_containers:
        args.append("-a")
    args.extend(["--format", "{{.Names}}\t{{.Status}}\t{{.Image}}"])
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        return stderr.decode().strip() or "Unable to query Docker containers."
    return stdout.decode().strip()
