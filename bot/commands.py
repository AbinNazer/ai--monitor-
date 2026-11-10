import discord
import io
from discord.ext import commands

from collectors.prometheus_client import PrometheusClient
from collectors.k3s_client import get_pods
from logs_fetch.docker_logs import get_container_error_logs, get_container_logs, list_all_containers, list_containers
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
    pods = await get_pods()
    context = f"Host CPU: {cpu:.1f}%, Mem: {mem:.1f}%\nPods: {pods}"
    return await ask(question, context)


async def _send_log_result(channel, title: str, output: str):
    if len(output) <= 3800:
        await channel.send(embed=info_embed(title, f"```\n{output}\n```"))
    else:
        file = discord.File(io.BytesIO(output.encode()), filename="container-errors.txt")
        await channel.send(content=f"{title} — full results attached.", file=file)


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
        title = "All Docker containers" if include_stopped else "Running Docker containers"
        await message.channel.send(embed=info_embed(title, f"```\n{output or 'No containers found'}\n```"))
        return True

    if any(word in lower for word in ("pod", "kubernetes", "k8s")) and any(
        word in lower for word in ("show", "list", "running", "health", "status")
    ):
        pods = await get_pods()
        lines = [f"{p['name']} — {p['phase']} — restarts: {p['restarts']}" for p in pods]
        await message.channel.send(embed=info_embed("Pods", "\n".join(lines) or "No pods found"))
        return True

    if "log" in lower:
        words = text.split()
        marker = next((i for i, word in enumerate(words) if word.lower() in ("for", "of")), None)
        name = words[marker + 1] if marker is not None and marker + 1 < len(words) else (words[-1] if len(words) > 1 else "")
        if name:
            source = "k3s" if any(word in lower for word in ("pod", "kubernetes", "k8s")) else "docker"
            if source == "docker" and any(word in lower for word in ("error", "errors", "failed", "failure", "exception")):
                output = await get_container_error_logs(name)
                await _send_log_result(message.channel, f"Errors in {name} (last 24 hours)", output)
            else:
                output = await get_pod_logs(name) if source == "k3s" else await get_container_logs(name)
                await _send_log_result(message.channel, f"Logs: {name}", output[-3800:])
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
        await ctx.send(embed=info_embed("Containers", f"```\n{output}\n```"))

    @commands.hybrid_command(name="pods", aliases=["k8s"])
    async def pods(self, ctx: commands.Context):
        pods = await get_pods()
        lines = [f"{p['name']} — {p['phase']} — restarts: {p['restarts']}" for p in pods]
        await ctx.send(embed=info_embed("Pods", "\n".join(lines) or "No pods found"))

    @commands.hybrid_command(name="logs")
    async def logs(self, ctx: commands.Context, name: str, source: str = "docker"):
        if source == "k3s":
            output = await get_pod_logs(name)
        else:
            output = await get_container_logs(name)
        await ctx.send(embed=info_embed(f"Logs: {name}", f"```\n{output[-1800:]}\n```"))

    @commands.hybrid_command(name="ask")
    async def ask_cmd(self, ctx: commands.Context, *, question: str):
        answer = await _ask_question(question)
        await ctx.send(embed=info_embed("AI answer", answer))


async def setup(bot: commands.Bot):
    await bot.add_cog(MonitorCommands(bot))
