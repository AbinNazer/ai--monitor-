import pytest
from db.models import Alert


def test_alert_defaults():
    alert = Alert(target="test", alert_type="cpu_high")
    assert alert.status == "open"
    assert alert.breach_count == 1