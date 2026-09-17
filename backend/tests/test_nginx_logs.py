from src.services.monitoring.nginx_logs import NginxAccessLogReader


def test_log_reader_reports_request_rate_and_mean_response_time(tmp_path):
    access_log = tmp_path / "access.json"
    access_log.write_text(
        '{"request_time":"0.010","status":"200"}\n'
        '{"request_time":"0.030","status":"200"}\n',
        encoding="utf-8",
    )
    reader = NginxAccessLogReader(str(access_log), interval_seconds=5)
    reader.last_read -= 5

    metric = reader.read_window()

    assert metric["request_rate_per_second"] == 0.4
    assert metric["response_time_ms"] == 20.0
