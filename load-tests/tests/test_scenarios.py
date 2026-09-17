import pytest

from workloads.scenarios import workload_parameters


@pytest.mark.parametrize("scenario", ["stable", "gradual_increase", "sudden_spike", "sudden_drop", "periodic", "changing_workload"])
def test_each_supported_scenario_has_bounded_work(scenario):
    duration, intensity = workload_parameters(scenario, 5, 25, 10, 10)
    assert duration == 25
    assert 1 <= intensity <= 100


def test_unknown_scenario_is_rejected():
    with pytest.raises(ValueError):
        workload_parameters("unknown", 0, 25, 10, 10)
