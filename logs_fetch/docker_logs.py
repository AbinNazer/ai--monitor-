import asyncio


async def get_container_logs(name: str, tail: int = 50) -> str:
    proc = await asyncio.create_subprocess_exec(
        "docker", "logs", "--tail", str(tail), name,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    output = stdout.decode() + stderr.decode()
    return output[-4000:]  # cap size for LLM context


async def list_containers() -> str:
    proc = await asyncio.create_subprocess_exec(
        "docker", "ps", "--format", "{{.Names}}\t{{.Status}}\t{{.Image}}",
        stdout=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    return stdout.decode()