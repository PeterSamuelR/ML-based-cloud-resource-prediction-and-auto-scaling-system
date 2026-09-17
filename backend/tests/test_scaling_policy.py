from src.services.scaling.controller import ScalingController


def test_reactive_threshold_policy_decisions():
    controller = ScalingController(None, None, {"reactive": {"scale_out_cpu_threshold": 75, "scale_in_cpu_threshold": 35}, "predictive": {"scale_out_predicted_cpu_threshold": 75, "scale_in_predicted_cpu_threshold": 35}, "scaling": {"cooldown_seconds": 30, "min_replicas": 1, "max_replicas": 5}})
    assert controller.desired_action(80, "reactive")[0] == "scale_out"
    assert controller.desired_action(20, "reactive")[0] == "scale_in"
    assert controller.desired_action(50, "reactive")[0] == "none"


def test_predictive_threshold_policy_decisions():
    controller = ScalingController(None, None, {"reactive": {"scale_out_cpu_threshold": 75, "scale_in_cpu_threshold": 35}, "predictive": {"scale_out_predicted_cpu_threshold": 75, "scale_in_predicted_cpu_threshold": 35}, "scaling": {"cooldown_seconds": 30, "min_replicas": 1, "max_replicas": 5}})
    assert controller.desired_action(80, "predictive")[0] == "scale_out"
