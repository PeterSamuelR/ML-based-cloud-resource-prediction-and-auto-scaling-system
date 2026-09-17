import os
import time

from locust import HttpUser, between, task

from workloads.scenarios import workload_parameters


class CloudWorkloadUser(HttpUser):
    host = "http://localhost:8080"
    wait_time = between(float(os.getenv("LOCUST_WAIT_MIN_SECONDS", "0.1")), float(os.getenv("LOCUST_WAIT_MAX_SECONDS", "0.3")))

    def on_start(self):
        self.started_at = time.monotonic()

    @task
    def generate_work(self):
        duration, intensity = workload_parameters(
            os.getenv("LOCUST_WORKLOAD_SCENARIO", "stable"), time.monotonic() - self.started_at,
            int(os.getenv("LOCUST_WORK_DURATION_MS", "25")), int(os.getenv("LOCUST_WORK_INTENSITY", "10")),
            int(os.getenv("LOCUST_PHASE_SECONDS", "10")),
        )
        self.client.get("/work", params={"duration_ms": duration, "intensity": intensity}, name="/work")
