import asyncio


async def container_exists(name: str) -> bool:
    proc = await asyncio.create_subprocess_exec(
        "docker", "ps", "-a", "--format", "{{.Names}}",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    return name in stdout.decode(errors="replace").splitlines()


async def control_container(name: str, action: str) -> tuple[bool, str]:
    if action not in {"start", "stop", "restart"}:
        return False, f"Unsupported action: {action}"
    proc = await asyncio.create_subprocess_exec(
        "docker", action, name,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    output = (stdout + stderr).decode(errors="replace").strip()
    return proc.returncode == 0, output or f"docker {action} completed."
