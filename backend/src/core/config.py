from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = base.copy()
    for key, value in override.items():
        result[key] = _merge(result[key], value) if isinstance(value, dict) and isinstance(result.get(key), dict) else value
    return result


def load_config() -> dict[str, Any]:
    configured_directory = Path(os.getenv("CONFIG_DIRECTORY", "/config"))
    fallback_directory = Path(__file__).resolve().parents[3] / "config"
    config_directory = configured_directory if (configured_directory / "default.yaml").exists() else fallback_directory
    with (config_directory / "default.yaml").open(encoding="utf-8") as file:
        config = yaml.safe_load(file)
    # Both threshold sections are needed because a predictive deployment falls
    # back to the reactive baseline while no trained model is available.
    for policy_name in ("reactive", "predictive", "adaptive"):
        policy_file = config_directory / f"{policy_name}.yaml"
        if policy_file.exists():
            with policy_file.open(encoding="utf-8") as file:
                override = yaml.safe_load(file)
                # Policy files contribute their settings; the environment selects
                # the runtime policy and must not be overwritten by merge order.
                override.pop("policy", None)
                config = _merge(config, override)
    policy = os.getenv("AUTOSCALING_POLICY", "reactive")
    config["selected_policy"] = policy
    config["policy"] = policy
    return config
