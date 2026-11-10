import httpx
import config


class PrometheusClient:
    def __init__(self, base_url: str = config.PROMETHEUS_URL):
        self.base_url = base_url

    async def instant_query(self, promql: str) -> list[dict]:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{self.base_url}/api/v1/query", params={"query": promql})
            r.raise_for_status()
            data = r.json()
            if data["status"] != "success":
                return []
            return data["data"]["result"]

    async def container_cpu_percent(self) -> dict[str, float]:
        # cAdvisor: cpu usage rate per container over 1m, as percent of one core
        q = 'sum by (name) (rate(container_cpu_usage_seconds_total{name!=""}[1m])) * 100'
        result = await self.instant_query(q)
        return {r["metric"]["name"]: float(r["value"][1]) for r in result}

    async def container_mem_percent(self) -> dict[str, float]:
        q = '(container_memory_usage_bytes{name!=""} / container_spec_memory_limit_bytes{name!=""}) * 100'
        result = await self.instant_query(q)
        return {
            r["metric"]["name"]: float(r["value"][1])
            for r in result
            if r["value"][1] not in ("NaN", "+Inf")
        }

    async def container_restart_count(self) -> dict[str, float]:
        q = "container_last_seen{name!=\"\"} - container_start_time_seconds{name!=\"\"}"
        # placeholder metric; real restart count typically comes from Docker events or kube-state-metrics
        result = await self.instant_query(q)
        return {r["metric"]["name"]: float(r["value"][1]) for r in result}

    async def node_cpu_percent(self) -> float:
        q = '100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[1m])) * 100)'
        result = await self.instant_query(q)
        return float(result[0]["value"][1]) if result else 0.0

    async def node_mem_percent(self) -> float:
        q = '(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100'
        result = await self.instant_query(q)
        return float(result[0]["value"][1]) if result else 0.0

    async def node_disk_percent(self, mountpoint: str = "/") -> float:
        q = f'max((1 - (node_filesystem_avail_bytes{{mountpoint="{mountpoint}",fstype!~"tmpfs|overlay"}} / node_filesystem_size_bytes{{mountpoint="{mountpoint}",fstype!~"tmpfs|overlay"}})) * 100)'
        result = await self.instant_query(q)
        return max(0.0, min(100.0, float(result[0]["value"][1]))) if result else 0.0

    async def pod_restarts(self) -> dict[str, float]:
        # from kube-state-metrics
        q = "kube_pod_container_status_restarts_total"
        result = await self.instant_query(q)
        return {r["metric"].get("pod", "unknown"): float(r["value"][1]) for r in result}

    async def pod_not_ready(self) -> list[str]:
        q = 'kube_pod_status_ready{condition="false"} == 1'
        result = await self.instant_query(q)
        return [r["metric"].get("pod", "unknown") for r in result]
