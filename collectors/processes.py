import asyncio
from collections import defaultdict


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
            rows.append({
                "pid": fields[0],
                "user": fields[1],
                "cpu": float(fields[8]),
                "mem": float(fields[9]),
                "command": fields[11],
            })
        except ValueError:
            continue
    return rows[:limit]


async def get_top_processes(limit: int = 10) -> str:
    rows = await _top_rows(limit)
    if not rows:
        return "No VPS processes found."
    lines = ["**Top VPS processes by CPU**"]
    lines.extend(
        f"`{row['user']}` · PID `{row['pid']}` · CPU `{row['cpu']:.1f}%` · MEM `{row['mem']:.1f}%`\n"
        f"`{row['command'][:180]}`"
        for row in rows
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
    lines = ["**Top VPS users by process CPU**"]
    lines.extend(
        f"`{user}` · CPU `{values[0]:.1f}%` · MEM `{values[1]:.1f}%` · processes `{values[2]}`"
        for user, values in ranked
    )
    return "\n".join(lines)
