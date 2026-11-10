import discord


def alert_embed(target: str, alert_type: str, value, diagnosis: str) -> discord.Embed:
    embed = discord.Embed(
        title=f"🚨 {alert_type} — {target}",
        description=f"**Value:** {value}\n\n**AI diagnosis:**\n{diagnosis}",
        color=discord.Color.red(),
    )
    return embed

def info_embed(title: str, content: str) -> discord.Embed:
    embed = discord.Embed(title=title, description=content[:4000], color=discord.Color.blue())
    return embed

def batch_alert_embed(breaches: list[dict], diagnosis: str) -> discord.Embed:
    targets = ", ".join(b["target"] for b in breaches)
    embed = discord.Embed(
        title=f"🚨 {len(breaches)} alerts fired together — {targets}",
        description=f"**AI diagnosis:**\n{diagnosis}",
        color=discord.Color.orange(),
    )
    return embed