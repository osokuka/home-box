"""Reconnect / backoff policy for HLK-DIO16.

Hides failure bookkeeping so the coordinator only asks: next poll delay,
and whether to force a socket reset.
"""

from __future__ import annotations

try:
    from .const import (
        FORCE_RESET_AFTER_FAILURES,
        RECONNECT_BACKOFF_MAX_SECONDS,
        RECONNECT_BACKOFF_START_SECONDS,
        SCAN_INTERVAL_SECONDS,
    )
except ImportError:  # path-based unit tests
    from const import (  # type: ignore[no-redef]
        FORCE_RESET_AFTER_FAILURES,
        RECONNECT_BACKOFF_MAX_SECONDS,
        RECONNECT_BACKOFF_START_SECONDS,
        SCAN_INTERVAL_SECONDS,
    )


class ReconnectPolicy:
    """Track consecutive failures and compute the next poll interval."""

    def __init__(
        self,
        *,
        scan_interval: float = SCAN_INTERVAL_SECONDS,
        backoff_start: float = RECONNECT_BACKOFF_START_SECONDS,
        backoff_max: float = RECONNECT_BACKOFF_MAX_SECONDS,
        force_after: int = FORCE_RESET_AFTER_FAILURES,
    ) -> None:
        self._scan_interval = scan_interval
        self._backoff_start = backoff_start
        self._backoff_max = backoff_max
        self._force_after = force_after
        self.failures = 0
        self._delay = backoff_start

    @property
    def healthy_interval(self) -> float:
        """Poll interval while the device is reachable."""
        return self._scan_interval

    def on_success(self) -> float:
        """Reset after a good poll; return the healthy interval."""
        self.failures = 0
        self._delay = self._backoff_start
        return self._scan_interval

    def on_failure(self) -> tuple[float, bool]:
        """Record a failed poll.

        Returns (next_interval_seconds, force_socket_reset).
        """
        self.failures += 1
        delay = self._delay
        self._delay = min(self._delay * 2.0, self._backoff_max)
        force_reset = self.failures >= self._force_after and (
            self.failures == self._force_after or self.failures % self._force_after == 0
        )
        return delay, force_reset
