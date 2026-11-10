import pytest
from collectors.prometheus_client import PrometheusClient


@pytest.mark.asyncio
async def test_instant_query_handles_empty(monkeypatch):
    client = PrometheusClient()

    async def fake_query(self, promql):
        return []

    monkeypatch.setattr(PrometheusClient, "instant_query", fake_query)
    result = await client.container_cpu_percent()
    assert result == {}