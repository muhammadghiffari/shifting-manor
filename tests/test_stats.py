"""Statistics used by the evaluation report."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from shifting_manor.sim.stats import calibration, calibration_error, mcnemar, wilson_ci


def test_wilson_interval_brackets_the_rate():
    lo, hi = wilson_ci(50, 100)
    assert lo < 0.5 < hi
    assert 0.39 < lo < 0.41
    assert 0.59 < hi < 0.61
    assert wilson_ci(0, 10)[0] == 0.0
    assert wilson_ci(10, 10)[1] == 1.0
    assert wilson_ci(0, 0) == (0.0, 0.0)


def test_mcnemar_counts_discordant_pairs():
    a = [True, True, True, False, False, False, False, False, False, False]
    b = [False, False, False, True, False, False, False, False, False, False]
    result = mcnemar(a, b)
    assert result["a_only"] == 3
    assert result["b_only"] == 1
    assert 0.0 <= result["p"] <= 1.0

    same = mcnemar([True, False], [True, False])
    assert same["p"] == 1.0

    with pytest.raises(ValueError):
        mcnemar([True], [])


def test_calibration_bins_include_all_risk_values():
    records = [
        SimpleNamespace(
            gambles=[
                {"step_risk": 0.0, "died": False},
                {"step_risk": 0.05, "died": True},
                {"step_risk": 0.42, "died": False},
                {"step_risk": 1.0, "died": True},
            ]
        ),
        {"gambles": [{"step_risk": 0.99, "died": False}]},
    ]

    bins = calibration(records)

    assert [b["lo"] for b in bins] == list(range(0, 100, 10))
    assert bins[0]["n"] == 2 and bins[0]["deaths"] == 1
    assert bins[4]["n"] == 1 and bins[4]["deaths"] == 0
    assert bins[-1]["n"] == 2 and bins[-1]["deaths"] == 1
    assert calibration_error(bins) >= 0.0
