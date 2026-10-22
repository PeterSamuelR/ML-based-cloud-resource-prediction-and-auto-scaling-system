from src.main import next_collection_schedule


def test_sampling_schedule_waits_only_for_remaining_interval():
    scheduled, delay = next_collection_schedule(100.0, 103.0, 5.0)

    assert scheduled == 105.0
    assert delay == 2.0


def test_sampling_schedule_skips_missed_ticks_without_catchup_burst():
    scheduled, delay = next_collection_schedule(100.0, 107.0, 5.0)

    assert scheduled == 110.0
    assert delay == 3.0
