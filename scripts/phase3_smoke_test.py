"""Real Docker Compose smoke test for Nginx dynamic replica membership."""

from __future__ import annotations

import json
import subprocess
import time
import urllib.request

COMPOSE = ["docker", "compose"]


def command(*arguments: str) -> str:
    completed = subprocess.run(
        [*COMPOSE, *arguments], check=False, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"docker compose {' '.join(arguments)} failed:\n{completed.stdout}{completed.stderr}"
        )
    return completed.stdout


def docker_command(*arguments: str) -> str:
    completed = subprocess.run(
        ["docker", *arguments], check=False, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if completed.returncode != 0:
        raise RuntimeError(f"docker {' '.join(arguments)} failed:\n{completed.stdout}{completed.stderr}")
    return completed.stdout


def nginx_request() -> dict[str, object]:
    request = urllib.request.Request("http://127.0.0.1:8080/", headers={"Connection": "close"})
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read())


def wait_for_replicas(expected_count: int) -> None:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        try:
            seen = {str(nginx_request()["instance_id"]) for _ in range(expected_count * 8)}
            if len(seen) >= expected_count:
                print(f"Nginx reached {len(seen)} distinct replicas: {sorted(seen)}")
                return
        except Exception:
            pass
        time.sleep(2)
    raise RuntimeError(f"Nginx did not reach {expected_count} distinct healthy replicas in time.")


def main() -> None:
    try:
        command("up", "-d", "--build", "--scale", "application=2")
        wait_for_replicas(2)

        running = command(
            "ps", "-q", "application"
        ).splitlines()
        if len(running) != 2:
            raise RuntimeError(f"Expected two application replicas, found {len(running)}.")

        command("up", "-d", "--scale", "application=3")
        wait_for_replicas(3)
        running = command("ps", "-q", "application").splitlines()
        if len(running) != 3:
            raise RuntimeError(f"Expected dynamic scale-out to create three replicas, found {len(running)}.")

        containers = json.loads(docker_command("inspect", *running))
        for container in containers:
            required = container["Config"]["Labels"]
            assert required["com.ml-autoscaler.project"] == "cloud-resource-autoscaling"
            assert required["com.ml-autoscaler.role"] == "application"
            assert required["com.ml-autoscaler.managed"] == "true"

        target_ip = containers[0]["NetworkSettings"]["Networks"]["cloud-resource-autoscaling-network"]["IPAddress"]

        command("exec", "-T", "membership-controller", "python", "controller.py", "remove", running[0])
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            upstream = command("exec", "-T", "nginx", "cat", "/etc/nginx/generated/membership.conf")
            status = docker_command("inspect", "--format", "{{.State.Running}}", running[0]).strip()
            if target_ip not in upstream and status == "false":
                print("Safe removal verified: membership updated before target container stopped.")
                break
            time.sleep(1)
        else:
            raise RuntimeError("Safe removal did not complete in time.")
    finally:
        subprocess.run(
            [*COMPOSE, "down", "--remove-orphans", "--volumes"],
            check=False,
            encoding="utf-8",
            errors="replace",
        )


if __name__ == "__main__":
    main()
