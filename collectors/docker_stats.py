import asyncio
import json


async def get_container_stats() -> list[dict]:
    proc = await asyncio.create_subprocess_exec(
        "docker", "stats", "--no-stream", "--format", "{{json .}}",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(stderr.decode(errors="replace").strip() or "Unable to read Docker stats")
    stats = []
    for line in stdout.decode(errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
            stats.append({
                "name": item.get("Name", "unknown"),
                "cpu_percent": float(item.get("CPUPerc", "0%").strip("%")),
                "mem_percent": float(item.get("MemPerc", "0%").strip("%")),
                "mem_usage": item.get("MemUsage", ""),
            })
        except (json.JSONDecodeError, ValueError):
            continue
    return stats


async def top_cpu_container() -> dict | None:
    stats = await get_container_stats()
    return max(stats, key=lambda item: item["cpu_percent"]) if stats else None
