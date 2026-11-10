import discord
from discord.ext import commands

from collectors.prometheus_client import PrometheusClient
from collectors.k3s_client import get_pods
from logs_fetch.docker_logs import get_container_logs, list_containers
from logs_fetch.k3s_logs import get_pod_logs
from llm.client import ask
from bot.formatter import info_embed

prom = PrometheusClient()


class MonitorCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="status", aliases=["health"])
    async def status(self, ctx: commands.Context):
        cpu = await prom.node_cpu_percent()
        mem = await prom.node_mem_percent()
        disk = await prom.node_disk_percent()
        content = f"CPU: {cpu:.1f}%\nMem: {mem:.1f}%\nDisk: {disk:.1f}%"
        await ctx.send(embed=info_embed("Host status", content))

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
        cpu = await prom.node_cpu_percent()
        mem = await prom.node_mem_percent()
        pods = await get_pods()
        context = f"Host CPU: {cpu:.1f}%, Mem: {mem:.1f}%\nPods: {pods}"
        answer = await ask(question, context)
        await ctx.send(embed=info_embed("AI answer", answer))


async def setup(bot: commands.Bot):
    await bot.add_cog(MonitorCommands(bot))
