import discord
import io
import re
import config
from discord.ext import commands

from collectors.prometheus_client import PrometheusClient
from collectors.k3s_client import get_pod_ports, get_pods
from logs_fetch.docker_logs import get_container_error_logs, get_container_logs, get_container_ports, list_all_containers, list_containers, summarize_logs
from logs_fetch.k3s_logs import get_pod_logs
from llm.client import ask
from bot.formatter import info_embed

prom = PrometheusClient()


async def _status_embed():
    cpu = await prom.node_cpu_percent()
    mem = await prom.node_mem_percent()
    disk = await prom.node_disk_percent()
    return info_embed("Host status", f"CPU: {cpu:.1f}%\nMem: {mem:.1f}%\nDisk: {disk:.1f}%")


async def _ask_question(question: str):
    cpu = await prom.node_cpu_percent()
    mem = await prom.node_mem_percent()
    pods = await get_pods(namespace=config.K3S_NAMESPACE)
    context = f"Host CPU: {cpu:.1f}%, Mem: {mem:.1f}%\nPods: {pods}"
    return await ask(question, context)


async def _send_log_result(channel, title: str, output: str):
    lines = output.splitlines()
    preview = "\n".join(lines[-25:]) if len(lines) > 25 else output
    suffix = "\n\nFull output is attached." if len(lines) > 25 else ""
    embed = info_embed(title, f"```text\n{preview[-3600:]}\n```{suffix}")
    if len(lines) > 25:
        file = discord.File(io.BytesIO(output.encode()), filename="container-logs.txt")
        await channel.send(embed=embed, file=file)
    else:
        await channel.send(embed=embed)


async def _send_log_summary(channel, title: str, name: str, output: str):
    await channel.send(embed=info_embed(title, summarize_logs(output, name)))


def _format_containers(output: str, down_only: bool = False) -> list[str]:
    rows = []
    for line in output.splitlines():
        parts = line.split("\t", 2)
        if len(parts) == 3:
            name, status, image = parts
            marker = "UP" if status.lower().startswith("up") else "DOWN"
            if down_only and marker != "DOWN":
                continue
            rows.append((marker, name, status, image))
    if not rows:
        return ["No containers found."]
    return [f"{'🟢' if state == 'UP' else '🔴'} **{state}** `{name}`\n{status} · `{image}`" for state, name, status, image in rows]


async def _send_container_result(channel, title: str, output: str, down_only: bool = False):
    formatted = _format_containers(output, down_only=down_only)
    chunks, current = [], []
    size = 0
    for line in formatted:
        if current and size + len(line) + 2 > 3500:
            chunks.append("\n\n".join(current))
            current, size = [], 0
        current.append(line)
        size += len(line) + 2
    if current:
        chunks.append("\n\n".join(current))
    for index, chunk in enumerate(chunks, 1):
        suffix = f" ({index}/{len(chunks)})" if len(chunks) > 1 else ""
        await channel.send(embed=info_embed(f"{title}{suffix}", chunk))


async def handle_natural_message(message: discord.Message) -> bool:
    """Handle ordinary human-language messages in the configured channel."""
    text = message.content.strip()
    lower = text.lower()
    if not text or lower.startswith(("!", "/")):
        return False

    if any(word in lower for word in ("container", "docker")) and any(
        word in lower for word in ("show", "list", "running", "which", "status", "check", "are", "is")
    ):
        include_stopped = any(word in lower for word in ("down", "stopped", "exited", "not running", "all"))
        output = await (list_all_containers() if include_stopped else list_containers())
        down_only = any(word in lower for word in ("down", "stopped", "exited", "not running")) and "all" not in lower
        title = "Down Docker containers" if down_only else ("All Docker containers" if include_stopped else "Running Docker containers")
        await _send_container_result(message.channel, title, output, down_only=down_only)
        return True

    if any(word in lower for word in ("pod", "kubernetes", "k8s")) and any(
        word in lower for word in ("show", "list", "running", "health", "status")
    ):
        pods = await get_pods()
        lines = [f"`{p['namespace']}/{p['name']}` — {p['phase']} — restarts: {p['restarts']}" for p in pods]
        await message.channel.send(embed=info_embed("Pods", "\n".join(lines) or "No pods found"))
        return True

    is_error_log_request = any(word in lower for word in ("error", "errors", "exception", "failed", "failure")) and any(
        word in lower for word in ("for", "from", "of", "on", "in", "container")
    )
    if "log" in lower or is_error_log_request:
        words = text.split()
        marker = next((i for i, word in enumerate(words) if word.lower() in ("for", "from", "of", "on", "in")), None)
        name = words[marker + 1] if marker is not None and marker + 1 < len(words) else (words[-1] if len(words) > 1 else "")
        if name:
            source = "k3s" if any(word in lower for word in ("pod", "kubernetes", "k8s")) else "docker"
            full_requested = any(word in lower for word in ("full", "everything", "all lines", "complete"))
            if source == "docker" and any(word in lower for word in ("error", "errors", "failed", "failure", "exception")):
                output = await get_container_error_logs(name)
                if full_requested:
                    await _send_log_result(message.channel, f"Errors in {name} (last 24 hours)", output)
                else:
                    await _send_log_summary(message.channel, f"Errors in {name} (last 24 hours)", name, output)
            else:
                if source == "k3s":
                    namespace = config.K3S_NAMESPACE if config.K3S_NAMESPACE not in ("all", "*") else "default"
                    if "/" in name:
                        namespace, name = name.split("/", 1)
                    namespace_match = re.search(r"\b(?:in|namespace)\s+([\w.-]+)", lower)
                    if namespace_match:
                        namespace = namespace_match.group(1)
                    output = await get_pod_logs(name, namespace=namespace)
                else:
                    output = await get_container_logs(name)
                if full_requested:
                    await _send_log_result(message.channel, f"Logs: {name} (full)", output)
                else:
                    await _send_log_summary(message.channel, f"Logs: {name}", name, output)
            return True

    if any(word in lower for word in ("port", "ports")):
        words = text.rstrip("?.!").split()
        name = words[-1].strip("`.,") if len(words) > 1 else ""
        is_pod = any(word in lower for word in ("pod", "kubernetes", "k8s"))
        if is_pod:
            namespace = config.K3S_NAMESPACE if config.K3S_NAMESPACE not in ("all", "*") else "default"
            if "/" in name:
                namespace, name = name.split("/", 1)
            output = await get_pod_ports(name, namespace=namespace)
            await message.channel.send(embed=info_embed(f"Ports: {namespace}/{name}", f"```text\n{output}\n```"))
        else:
            output = await get_container_ports(name)
            await message.channel.send(embed=info_embed(f"Ports: {name}", f"```text\n{output}\n```"))
        return True

    if any(word in lower for word in ("status", "health", "cpu", "memory", "ram", "disk")) and not any(
        word in lower for word in ("why", "explain", "how", "what should")
    ):
        await message.channel.send(embed=await _status_embed())
        return True

    answer = await _ask_question(text)
    await message.channel.send(embed=info_embed("AI answer", answer))
    return True


class MonitorCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="status", aliases=["health"])
    async def status(self, ctx: commands.Context):
        await ctx.send(embed=await _status_embed())

    @commands.hybrid_command(name="containers", aliases=["docker"])
    async def containers(self, ctx: commands.Context):
        output = await list_containers()
        await _send_container_result(ctx.channel, "Running Docker containers", output)

    @commands.hybrid_command(name="pods", aliases=["k8s"])
    async def pods(self, ctx: commands.Context):
        pods = await get_pods(namespace=config.K3S_NAMESPACE)
        lines = [f"{p['name']} — {p['phase']} — restarts: {p['restarts']}" for p in pods]
        await ctx.send(embed=info_embed("Pods", "\n".join(lines) or "No pods found"))

    @commands.hybrid_command(name="logs")
    async def logs(self, ctx: commands.Context, name: str, mode: str = "summary", source: str = "docker"):
        if source == "k3s":
            output = await get_pod_logs(name)
        else:
            output = await get_container_logs(name)
        if mode.lower() == "full":
            await _send_log_result(ctx.channel, f"Logs: {name} (full)", output)
        else:
            await _send_log_summary(ctx.channel, f"Logs: {name}", name, output)

    @commands.hybrid_command(name="ask")
    async def ask_cmd(self, ctx: commands.Context, *, question: str):
        answer = await _ask_question(question)
        await ctx.send(embed=info_embed("AI answer", answer))


async def setup(bot: commands.Bot):
    await bot.add_cog(MonitorCommands(bot))
