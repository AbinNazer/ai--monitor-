from rules import thresholds


def evaluate_containers(container_stats: list[dict]) -> list[dict]:
    breaches = []
    for stats in container_stats:
        if stats["cpu_percent"] >= thresholds.CPU_PERCENT_THRESHOLD:
            breaches.append({"target": stats["name"], "alert_type": "cpu_high", "value": stats["cpu_percent"]})
        if stats["mem_percent"] >= thresholds.MEM_PERCENT_THRESHOLD:
            breaches.append({"target": stats["name"], "alert_type": "mem_high", "value": stats["mem_percent"]})
    return breaches


def evaluate_container_states(containers, persisted, now, grace_seconds):
    current = {c["name"] for c in containers}
    breaches = []
    for c in containers:
        state = persisted.get(c["name"])
        if c.get("state") == "exited" and c.get("exit_code", 0) != 0 and state and state.missing_since:
            if (now - state.missing_since).total_seconds() >= grace_seconds:
                breaches.append({"target": c["name"], "alert_type": "container_down", "value": c["status"]})
    for name, state in persisted.items():
        if name not in current and state.missing_since and (now - state.missing_since).total_seconds() >= grace_seconds:
            breaches.append({"target": name, "alert_type": "container_down", "value": "missing from Docker"})
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


def evaluate_pod_states(pods, persisted, now, grace_seconds):
    breaches = []
    for pod in pods:
        key = f"{pod['namespace']}/{pod['name']}"
        state = persisted.get(key)
        bad = pod["waiting_reason"] in thresholds.POD_CRASHLOOP_REASONS or pod["restarts"] >= thresholds.POD_RESTART_THRESHOLD
        if bad and state and state.bad_since and (now - state.bad_since).total_seconds() >= grace_seconds:
            alert_type = "pod_crashloop" if pod["waiting_reason"] in thresholds.POD_CRASHLOOP_REASONS else "pod_restart_high"
            breaches.append({"target": key, "alert_type": alert_type, "value": pod["waiting_reason"] or pod["restarts"]})
    return breaches
