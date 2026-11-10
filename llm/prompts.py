SYSTEM_PROMPT = (
    "You are a terse SRE assistant monitoring a VPS running Docker containers and K3s. "
    "Given an alert and recent logs, respond in under 6 lines with: "
    "1) what broke, 2) likely root cause, 3) a concrete suggested fix or command. "
    "No filler, no disclaimers."
)


def build_user_prompt(alert_text: str, logs: str) -> str:
    return f"ALERT:\n{alert_text}\n\nRECENT LOGS/CONTEXT:\n{logs or 'none available'}"

def build_batch_prompt(breaches: list[dict], logs_by_target: dict[str, str]) -> str:
    sections = []
    for b in breaches:
        target = b["target"]
        logs = logs_by_target.get(target, "none available")
        sections.append(
            f"--- TARGET: {target} | TYPE: {b['alert_type']} | VALUE: {b['value']} ---\n"
            f"LOGS:\n{logs[:1500]}"
        )
    joined = "\n\n".join(sections)
    return (
        f"{len(breaches)} alerts fired in the same check cycle. "
        f"Diagnose each one separately, using this format per target:\n"
        f"[target]: cause → fix (one line each)\n"
        f"If they look related (e.g. same root cause cascading), say so at the end in one line.\n\n"
        f"{joined}"
    )