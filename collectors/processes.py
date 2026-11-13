import asyncio
from collections import defaultdict
import os


async def _top_rows(limit: int = 10) -> list[dict]:
    proc = await asyncio.create_subprocess_exec(
        "top", "-b", "-n", "1", "-o", "%CPU",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(stderr.decode(errors="replace").strip() or "Unable to read VPS processes")

    lines = stdout.decode(errors="replace").splitlines()
    header_index = next((i for i, line in enumerate(lines) if line.strip().startswith("PID ")), None)
    if header_index is None:
        return []

    rows = []
    for line in lines[header_index + 1:]:
        fields = line.split(None, 11)
        if len(fields) < 12:
            continue
        try:
            command = fields[11]
            if os.path.basename(command.split()[0]) in {"top", "ps"}:
                continue
            rows.append({
                "pid": fields[0],
                "user": fields[1],
                "cpu": float(fields[8]),
                "mem": float(fields[9]),
                "command": command,
            })
        except ValueError:
            continue
    return rows[:limit]


async def get_top_processes(limit: int = 10) -> str:
    rows = await _top_rows(limit)
    if not rows:
        return "No VPS processes found."
    lines = ["**Top VPS processes**", "Ranked by current CPU usage.\n"]
    for rank, row in enumerate(rows, 1):
        command = os.path.basename(row["command"].split()[0]) if row["command"] else "unknown"
        details = row["command"][:140]
        lines.append(
            f"**{rank}. {command}**\n"
            f"User: `{row['user']}` · PID: `{row['pid']}`\n"
            f"CPU: **{row['cpu']:.1f}%** · Memory: **{row['mem']:.1f}%**\n"
            f"Command: `{details}`"
        )
    return "\n\n".join(lines)


async def get_top_users(limit: int = 10) -> str:
    rows = await _top_rows(100)
    totals = defaultdict(lambda: [0.0, 0.0, 0])
    for row in rows:
        totals[row["user"]][0] += row["cpu"]
        totals[row["user"]][1] += row["mem"]
        totals[row["user"]][2] += 1
    ranked = sorted(totals.items(), key=lambda item: item[1][0], reverse=True)[:limit]
    if not ranked:
        return "No VPS users found."
    lines = ["**Top VPS users**", "Ranked by combined process CPU usage.\n"]
    lines.extend(
        f"**{index}. `{user}`**\n"
        f"CPU: **{values[0]:.1f}%** · Memory: **{values[1]:.1f}%** · Processes: `{values[2]}`"
        for index, (user, values) in enumerate(ranked, 1)
    )
    return "\n".join(lines)
