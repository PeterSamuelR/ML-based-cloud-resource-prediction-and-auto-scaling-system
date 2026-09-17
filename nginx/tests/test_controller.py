import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parents[1] / "membership-controller"))

from controller import PROJECT_LABELS, render_membership_config


def test_required_labels_are_locked() -> None:
    assert PROJECT_LABELS == {
        "com.ml-autoscaler.project": "cloud-resource-autoscaling",
        "com.ml-autoscaler.role": "application",
        "com.ml-autoscaler.managed": "true",
    }


def test_empty_healthy_membership_returns_safe_fallback() -> None:
    rendered = render_membership_config([], "cloud-resource-autoscaling-network")

    assert "return 503" in rendered
    assert "upstream application_upstream" not in rendered


def test_healthy_membership_renders_only_discovered_replica_addresses() -> None:
    first = SimpleNamespace(
        attrs={"NetworkSettings": {"Networks": {"cloud-resource-autoscaling-network": {"IPAddress": "172.31.0.2"}}}}
    )
    second = SimpleNamespace(
        attrs={"NetworkSettings": {"Networks": {"cloud-resource-autoscaling-network": {"IPAddress": "172.31.0.3"}}}}
    )

    rendered = render_membership_config([first, second], "cloud-resource-autoscaling-network")

    assert "server 172.31.0.2:8000;" in rendered
    assert "server 172.31.0.3:8000;" in rendered
    assert "proxy_pass http://application_upstream;" in rendered
