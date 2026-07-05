"""Unit tests for the EWMA latency tracker."""

from __future__ import annotations

import threading

import pytest

from aiplatform.router.latency import LatencyTracker


def test_estimate_returns_default_for_unseen_model() -> None:
    tracker = LatencyTracker()
    assert tracker.estimate("gpt-4o") == 1_000.0


def test_record_single_observation_with_alpha_one() -> None:
    tracker = LatencyTracker(alpha=1.0)
    tracker.record("gpt-4o", 500.0)
    assert tracker.estimate("gpt-4o") == pytest.approx(500.0)


def test_ewma_smoothes_observations() -> None:
    tracker = LatencyTracker(alpha=0.5)
    tracker.record("gpt-4o", 1_000.0)
    tracker.record("gpt-4o", 0.0)  # 0.5*0 + 0.5*1000 = 500
    assert tracker.estimate("gpt-4o") == pytest.approx(500.0)


def test_ewma_converges_toward_new_values() -> None:
    tracker = LatencyTracker(alpha=0.5)
    for _ in range(20):
        tracker.record("model-a", 200.0)
    assert tracker.estimate("model-a") == pytest.approx(200.0, abs=1.0)


def test_multiple_models_tracked_independently() -> None:
    tracker = LatencyTracker(alpha=1.0)
    tracker.record("fast-model", 100.0)
    tracker.record("slow-model", 3_000.0)
    assert tracker.estimate("fast-model") == pytest.approx(100.0)
    assert tracker.estimate("slow-model") == pytest.approx(3_000.0)


def test_reset_removes_model_estimate() -> None:
    tracker = LatencyTracker(alpha=1.0)
    tracker.record("gpt-4o", 400.0)
    tracker.reset("gpt-4o")
    assert tracker.estimate("gpt-4o") == 1_000.0


def test_all_estimates_returns_snapshot() -> None:
    tracker = LatencyTracker(alpha=1.0)
    tracker.record("a", 100.0)
    tracker.record("b", 200.0)
    snap = tracker.all_estimates()
    assert snap["a"] == pytest.approx(100.0)
    assert snap["b"] == pytest.approx(200.0)


def test_invalid_alpha_raises() -> None:
    with pytest.raises(ValueError):
        LatencyTracker(alpha=0.0)
    with pytest.raises(ValueError):
        LatencyTracker(alpha=1.5)


def test_thread_safety() -> None:
    tracker = LatencyTracker(alpha=0.1)
    errors: list[Exception] = []

    def _writer() -> None:
        try:
            for _ in range(100):
                tracker.record("shared-model", 500.0)
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=_writer) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors
    assert tracker.estimate("shared-model") > 0
