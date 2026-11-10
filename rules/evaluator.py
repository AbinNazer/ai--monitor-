from rules import thresholds


def evaluate_containers(cpu: dict[str, float], mem: dict[str, float]) -> list[dict]:
    breaches = []
    for name, val in cpu.items():
        if val >= thresholds.CPU_PERCENT_THRESHOLD:
            breaches.append({"target": name, "alert_type": "cpu_high", "value": val})
    for name, val in mem.items():
        if val >= thresholds.MEM_PERCENT_THRESHOLD:
            breaches.append({"target": name, "alert_type": "mem_high", "value": val})
    return breaches


def evaluate_node(node_cpu: float, node_mem: float, node_disk: float) -> list[dict]:
    breaches = []
    if node_cpu >= thresholds.CPU_PERCENT_THRESHOLD:
        breaches.append({"target": "host", "alert_type": "node_cpu_high", "value": node_cpu})
    if node_mem >= thresholds.MEM_PERCENT_THRESHOLD:
        breaches.append({"target": "host", "alert_type": "node_mem_high", "value": node_mem})
    if node_disk >= thresholds.DISK_PERCENT_THRESHOLD:
        breaches.append({"target": "host", "alert_type": "node_disk_high", "value": node_disk})
    return breaches


def evaluate_pods(pods: list[dict]) -> list[dict]:
    breaches = []
    for pod in pods:
        if pod["waiting_reason"] in thresholds.POD_CRASHLOOP_REASONS:
            breaches.append({
                "target": pod["name"],
                "alert_type": "pod_crashloop",
                "value": pod["waiting_reason"],
            })
        elif pod["restarts"] >= thresholds.POD_RESTART_THRESHOLD:
            breaches.append({
                "target": pod["name"],
                "alert_type": "pod_restart_high",
                "value": pod["restarts"],
            })
    return breaches