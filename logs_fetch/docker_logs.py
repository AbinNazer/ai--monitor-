import asyncio
import json
import re


async def get_container_logs(name: str, tail: int = 50) -> str:
    proc = await asyncio.create_subprocess_exec(
        "docker", "logs", "--tail", str(tail), name,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    output = stdout.decode() + stderr.decode()
    return output[-4000:]  # cap size for LLM context


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
    return "\n".join(matches) or "No error lines found in the last 24 hours."


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
        states.append({"name": item.get("Names", "unknown"), "status": status,
                       "image": item.get("Image", "unknown"),
                       "running": status.lower().startswith("up")})
    return states


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
