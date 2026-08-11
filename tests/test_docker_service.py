from datetime import UTC, datetime, timedelta

from api.services.docker_service import _cpu_percent, _memory_stats, _uptime_seconds


def _stats(total_usage: int, precpu_total_usage: int, system_usage: int, presystem_usage: int) -> dict:
    return {
        "cpu_stats": {
            "cpu_usage": {"total_usage": total_usage},
            "system_cpu_usage": system_usage,
            "online_cpus": 2,
        },
        "precpu_stats": {
            "cpu_usage": {"total_usage": precpu_total_usage},
            "system_cpu_usage": presystem_usage,
        },
        "memory_stats": {},
    }


def test_cpu_percent_computes_expected_value() -> None:
    stats = _stats(
        total_usage=2_000_000_000,
        precpu_total_usage=1_000_000_000,
        system_usage=100_000_000_000,
        presystem_usage=90_000_000_000,
    )
    assert _cpu_percent(stats) == 20.0


def test_cpu_percent_zero_deltas_returns_zero() -> None:
    stats = _stats(total_usage=1, precpu_total_usage=1, system_usage=1, presystem_usage=1)
    assert _cpu_percent(stats) == 0.0


def test_cpu_percent_missing_fields_returns_zero() -> None:
    assert _cpu_percent({}) == 0.0


def test_memory_stats_subtracts_cache() -> None:
    stats = {
        "memory_stats": {
            "usage": 104_857_600,  # 100 MB
            "limit": 1_073_741_824,  # 1024 MB
            "stats": {"cache": 10_485_760},  # 10 MB
        }
    }
    usage_mb, limit_mb, mem_percent = _memory_stats(stats)
    assert usage_mb == 90.0
    assert limit_mb == 1024.0
    assert mem_percent == 8.79


def test_memory_stats_missing_fields_defaults_to_zero() -> None:
    usage_mb, _limit_mb, mem_percent = _memory_stats({})
    assert usage_mb == 0.0
    assert mem_percent == 0.0


def test_uptime_seconds_zero_value_timestamp_is_zero() -> None:
    assert _uptime_seconds("0001-01-01T00:00:00Z") == 0


def test_uptime_seconds_recent_timestamp() -> None:
    started_at = (datetime.now(UTC) - timedelta(seconds=5)).isoformat().replace("+00:00", "Z")
    uptime = _uptime_seconds(started_at)
    assert 4 <= uptime <= 15
