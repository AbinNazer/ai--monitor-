import asyncio


async def get_pod_logs(name: str, namespace: str = "default", tail: int = 50) -> str:
    proc = await asyncio.create_subprocess_exec(
        "kubectl", "logs", name, "-n", namespace, "--tail", str(tail),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    output = stdout.decode(errors="replace") + stderr.decode(errors="replace")
    return output[-4000:]
