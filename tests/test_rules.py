from rules.evaluator import evaluate_containers, evaluate_pods


def test_cpu_breach():
    breaches = evaluate_containers([{"name": "app1", "cpu_percent": 95.0, "mem_percent": 0.0}])
    assert any(b["alert_type"] == "cpu_high" for b in breaches)


def test_no_breach():
    breaches = evaluate_containers([{"name": "app1", "cpu_percent": 10.0, "mem_percent": 10.0}])
    assert breaches == []


def test_pod_crashloop():
    pods = [{"name": "p1", "phase": "Running", "restarts": 0, "waiting_reason": "CrashLoopBackOff"}]
    breaches = evaluate_pods(pods)
    assert breaches[0]["alert_type"] == "pod_crashloop"
