"""Docker-label-scoped Nginx upstream membership controller.

This component performs membership synchronization only. It makes no
autoscaling decisions. Its explicit ``remove`` operation is a safe manual
scale-in primitive: remove from Nginx, validate/reload, then stop the replica.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import docker
from docker.models.containers import Container

PROJECT_LABELS = {
    "com.ml-autoscaler.project": "cloud-resource-autoscaling",
    "com.ml-autoscaler.role": "application",
    "com.ml-autoscaler.managed": "true",
}
RUNTIME_CONFIG_PATH = Path("/runtime/membership.conf")
NGINX_CONTAINER_LABEL = os.getenv("NGINX_CONTAINER_LABEL", "com.docker.compose.service=nginx")


def is_healthy_application(container: Container) -> bool:
    """Return True only for running, healthy containers with all required labels."""
    container.reload()
    labels = container.labels or {}
    state = container.attrs.get("State", {})
    health = state.get("Health", {}).get("Status")
    return (
        all(labels.get(key) == value for key, value in PROJECT_LABELS.items())
        and state.get("Running") is True
        and health == "healthy"
    )


def application_containers(client: docker.DockerClient, excluded_id: str | None = None) -> list[Container]:
    """Discover healthy project application replicas, optionally excluding one."""
    filters = {"label": [f"{key}={value}" for key, value in PROJECT_LABELS.items()]}
    containers = client.containers.list(filters=filters)
    return sorted(
        (
            container
            for container in containers
            if container.id != excluded_id and is_healthy_application(container)
        ),
        key=lambda container: container.name,
    )


def replica_address(container: Container, network_name: str) -> str:
    networks = container.attrs.get("NetworkSettings", {}).get("Networks", {})
    address = networks.get(network_name, {}).get("IPAddress")
    if not address:
        raise RuntimeError(f"Healthy application container {container.name} has no address on {network_name}.")
    return address


def render_membership_config(containers: list[Container], network_name: str) -> str:
    """Render either a safe no-replica response or a proxying upstream config."""
    if not containers:
        return """server {
    listen 80 default_server;
    server_name _;
    location / { return 503; }
}
"""

    servers = "\n".join(f"    server {replica_address(container, network_name)}:8000;" for container in containers)
    return f"""upstream application_upstream {{
{servers}
}}

server {{
    listen 80 default_server;
    server_name _;
    location / {{
        proxy_pass http://application_upstream;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
    }}
}}
"""


def nginx_container(client: docker.DockerClient) -> Container:
    key, value = NGINX_CONTAINER_LABEL.split("=", maxsplit=1)
    containers = client.containers.list(filters={"label": f"{key}={value}"})
    if len(containers) != 1:
        raise RuntimeError(f"Expected exactly one Nginx container, found {len(containers)}.")
    return containers[0]


def run_nginx_command(container: Container, command: list[str]) -> None:
    result = container.exec_run(command)
    if result.exit_code != 0:
        output = result.output.decode(errors="replace")
        raise RuntimeError(f"Nginx command failed ({' '.join(command)}): {output}")


def apply_membership(client: docker.DockerClient, excluded_id: str | None = None) -> list[Container]:
    """Write a candidate config, validate it, then gracefully reload Nginx.

    The previous file is restored when validation or reload fails, leaving the
    active Nginx process on its previous known-good configuration.
    """
    replicas = application_containers(client, excluded_id=excluded_id)
    candidate = render_membership_config(replicas, os.environ["APPLICATION_NETWORK"])
    previous = RUNTIME_CONFIG_PATH.read_text() if RUNTIME_CONFIG_PATH.exists() else None
    temporary = RUNTIME_CONFIG_PATH.with_suffix(".candidate")
    temporary.write_text(candidate)
    temporary.replace(RUNTIME_CONFIG_PATH)

    try:
        nginx = nginx_container(client)
        run_nginx_command(nginx, ["nginx", "-t"])
        run_nginx_command(nginx, ["nginx", "-s", "reload"])
    except Exception:
        if previous is None:
            RUNTIME_CONFIG_PATH.unlink(missing_ok=True)
        else:
            RUNTIME_CONFIG_PATH.write_text(previous)
        raise
    return replicas


def safe_remove(client: docker.DockerClient, container_id: str) -> None:
    """Remove a healthy replica from active membership before stopping it."""
    target = client.containers.get(container_id)
    if not is_healthy_application(target):
        raise RuntimeError("Only a currently healthy, managed application replica can be safely removed.")
    apply_membership(client, excluded_id=target.id)
    target.stop(timeout=10)
    target.remove()


def watch(client: docker.DockerClient) -> None:
    interval_seconds = float(os.getenv("SYNC_INTERVAL_SECONDS", "2"))
    last_config: str | None = None
    while True:
        try:
            replicas = application_containers(client)
            rendered = render_membership_config(replicas, os.environ["APPLICATION_NETWORK"])
            if rendered != last_config:
                apply_membership(client)
                last_config = rendered
                print(f"Applied Nginx membership for {len(replicas)} healthy application replicas.", flush=True)
        except Exception as error:
            print(f"Membership synchronization failed: {error}", file=sys.stderr, flush=True)
        time.sleep(interval_seconds)


def main() -> None:
    client = docker.from_env()
    command = sys.argv[1] if len(sys.argv) > 1 else "watch"
    if command == "watch":
        watch(client)
    elif command == "sync":
        apply_membership(client)
    elif command == "remove" and len(sys.argv) == 3:
        safe_remove(client, sys.argv[2])
    else:
        raise SystemExit("Usage: controller.py watch | controller.py sync | controller.py remove <container-id>")


if __name__ == "__main__":
    main()
