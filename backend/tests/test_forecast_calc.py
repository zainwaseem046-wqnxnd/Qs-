"""Golden-value tests for the forecasting engine."""

from decimal import Decimal as D

import pytest

from app.domains.cost_management.calc import forecast_line, project_forecast


@pytest.mark.parametrize(("method", "ctc"), [
    ("budget_remaining", "60000.00"),      # 400,000 - 340,000
    ("committed_remaining", "85000.00"),   # 425,000 - 340,000
    ("greater_of", "85000.00"),            # committed exceeds budget: forecast cannot be below commitments
])
def test_methods(method: str, ctc: str) -> None:
    line = forecast_line(method, D("400000.00"), D("425000.00"), D("340000.00"))
    assert line.cost_to_complete == D(ctc)
    assert line.final_cost == D("340000.00") + D(ctc)


def test_never_negative_and_overrun_variance() -> None:
    line = forecast_line("greater_of", D("100000.00"), D("90000.00"), D("120000.00"))
    assert line.cost_to_complete == D("0.00") and line.final_cost == D("120000.00")
    assert line.variance == D("-20000.00")


def test_manual() -> None:
    assert forecast_line("manual", D("10"), D("0"), D("5"), D("7.50")).final_cost == D("12.50")
    with pytest.raises(ValueError):
        forecast_line("manual", D("10"), D("0"), D("5"), None)
    with pytest.raises(ValueError):
        forecast_line("bogus", D("10"), D("0"), D("5"))


def test_project_totals_margin_and_earned_revenue() -> None:
    lines = [
        forecast_line("greater_of", D("400000.00"), D("425000.00"), D("340000.00")),  # FFC 425,000
        forecast_line("budget_remaining", D("250000.00"), D("180000.00"), D("100000.00")),  # FFC 250,000
        forecast_line("manual", D("0.00"), D("0.00"), D("5000.00"), D("0.00")),  # uncoded, FFC 5,000
    ]
    p = project_forecast(lines, D("792125.00"), D("-12125.00"))
    assert p.revenue == D("780000.00")
    assert p.final_cost == D("680000.00") and p.cost_to_date == D("445000.00")
    assert p.gross_profit == D("100000.00")
    assert p.margin_percent == D("12.82")            # 100,000 / 780,000 = 12.8205...
    assert p.percent_complete == D("65.44")          # 445,000 / 680,000 = 65.441...
    assert p.earned_revenue == D("510441.18")        # 780,000 x 445,000 / 680,000 = 510,441.176...
    assert p.variance == D("-30000.00")


def test_zero_revenue_and_cost() -> None:
    p = project_forecast([], D("0"), D("0"))
    assert p.margin_percent is None and p.percent_complete is None and p.earned_revenue is None
