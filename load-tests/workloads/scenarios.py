import math


def workload_parameters(scenario: str, elapsed_seconds: float, base_duration_ms: int, base_intensity: int, phase_seconds: int) -> tuple[int, int]:
    phase = max(1, phase_seconds)
    progress = min(1.0, (elapsed_seconds % phase) / phase)
    if scenario == "stable":
        intensity = base_intensity
    elif scenario == "gradual_increase":
        intensity = base_intensity + round(base_intensity * 4 * progress)
    elif scenario == "sudden_spike":
        intensity = base_intensity if elapsed_seconds < phase else base_intensity * 5
    elif scenario == "sudden_drop":
        intensity = base_intensity * 5 if elapsed_seconds < phase else base_intensity
    elif scenario == "periodic":
        intensity = base_intensity + round(base_intensity * 4 * ((math.sin(elapsed_seconds / phase * 2 * math.pi) + 1) / 2))
    elif scenario == "changing_workload":
        intensity = base_intensity * (1 if progress < 0.33 else 5 if progress < 0.66 else 2)
    else:
        raise ValueError(f"Unsupported workload scenario: {scenario}")
    return base_duration_ms, max(1, min(100, intensity))
