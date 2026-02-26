import uuid
from datetime import datetime, timezone

from pulsecheck.checker.distributed import DistributedChecker
from pulsecheck.models.health_check import HealthCheck, HealthStatus


def _make_check(status: HealthStatus) -> HealthCheck:
    return HealthCheck(
        id=uuid.uuid4(),
        service_id=uuid.uuid4(),
        region_id=uuid.uuid4(),
        status=status,
        response_time_ms=100,
        checked_at=datetime.now(timezone.utc),
    )


class TestConsensus:
    def test_all_healthy_returns_healthy(self):
        checks = [_make_check(HealthStatus.healthy) for _ in range(3)]
        assert DistributedChecker._compute_consensus(checks) == HealthStatus.healthy

    def test_majority_down_returns_down(self):
        checks = [
            _make_check(HealthStatus.down),
            _make_check(HealthStatus.down),
            _make_check(HealthStatus.healthy),
        ]
        assert DistributedChecker._compute_consensus(checks) == HealthStatus.down

    def test_single_region_failure_returns_degraded(self):
        checks = [
            _make_check(HealthStatus.healthy),
            _make_check(HealthStatus.healthy),
            _make_check(HealthStatus.down),
        ]
        assert DistributedChecker._compute_consensus(checks) == HealthStatus.degraded

    def test_all_down_returns_down(self):
        checks = [_make_check(HealthStatus.down) for _ in range(3)]
        assert DistributedChecker._compute_consensus(checks) == HealthStatus.down

    def test_all_degraded_returns_degraded(self):
        checks = [_make_check(HealthStatus.degraded) for _ in range(3)]
        assert DistributedChecker._compute_consensus(checks) == HealthStatus.degraded

    def test_empty_checks_returns_down(self):
        assert DistributedChecker._compute_consensus([]) == HealthStatus.down

    def test_mixed_degraded_and_healthy_returns_degraded(self):
        checks = [
            _make_check(HealthStatus.healthy),
            _make_check(HealthStatus.degraded),
            _make_check(HealthStatus.healthy),
        ]
        assert DistributedChecker._compute_consensus(checks) == HealthStatus.degraded

    def test_two_regions_one_down_returns_degraded(self):
        """With 2 regions, 1 down is not majority (1 <= 1), so degraded."""
        checks = [
            _make_check(HealthStatus.healthy),
            _make_check(HealthStatus.down),
        ]
        assert DistributedChecker._compute_consensus(checks) == HealthStatus.degraded

    def test_two_regions_both_down_returns_down(self):
        checks = [
            _make_check(HealthStatus.down),
            _make_check(HealthStatus.down),
        ]
        assert DistributedChecker._compute_consensus(checks) == HealthStatus.down

    def test_single_region_down_returns_down(self):
        """With 1 region, 1 down is majority."""
        checks = [_make_check(HealthStatus.down)]
        assert DistributedChecker._compute_consensus(checks) == HealthStatus.down

    def test_single_region_healthy_returns_healthy(self):
        checks = [_make_check(HealthStatus.healthy)]
        assert DistributedChecker._compute_consensus(checks) == HealthStatus.healthy


class TestAvgResponseTime:
    def test_avg_of_multiple(self):
        checks = [_make_check(HealthStatus.healthy) for _ in range(3)]
        checks[0].response_time_ms = 100
        checks[1].response_time_ms = 200
        checks[2].response_time_ms = 300
        assert DistributedChecker._avg_response_time(checks) == 200

    def test_avg_with_none(self):
        checks = [_make_check(HealthStatus.healthy) for _ in range(3)]
        checks[0].response_time_ms = 100
        checks[1].response_time_ms = None
        checks[2].response_time_ms = 300
        assert DistributedChecker._avg_response_time(checks) == 200

    def test_all_none_returns_none(self):
        checks = [_make_check(HealthStatus.healthy) for _ in range(3)]
        for c in checks:
            c.response_time_ms = None
        assert DistributedChecker._avg_response_time(checks) is None
