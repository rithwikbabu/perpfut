import pytest

from perpfut.portfolio_optimizer import (
    PortfolioOptimizationConfig,
    load_sleeve_return_stream,
    optimize_strategy_portfolio,
)


def _sleeve(
    strategy_instance_id: str,
    returns: list[float],
    *,
    strategy_id: str = "momentum",
) -> dict:
    return {
        "strategy_instance_id": strategy_instance_id,
        "strategy_id": strategy_id,
        "dataset_id": "dataset-1",
        "config_fingerprint": f"{strategy_instance_id}-fingerprint",
        "daily_returns": [
            {"label": f"2026-03-{day:02d}", "value": value}
            for day, value in enumerate(returns, start=1)
        ],
    }


def test_optimizer_enforces_long_only_caps_and_cash_residual() -> None:
    sleeves = [
        load_sleeve_return_stream(_sleeve("mom-a", [0.01, 0.02, 0.03])),
        load_sleeve_return_stream(_sleeve("mom-b", [0.01, 0.02, 0.025])),
        load_sleeve_return_stream(_sleeve("mom-c", [0.01, 0.015, 0.02])),
    ]

    result = optimize_strategy_portfolio(
        sleeves,
        config=PortfolioOptimizationConfig(
            lookback_days=2,
            max_strategy_weight=0.30,
            turnover_cost_bps=0.0,
        ),
    )

    third_day = result.weight_history[2]
    assert all(0.0 <= weight <= 0.30 + 1e-12 for weight in third_day.weights.values())
    assert third_day.gross_weight <= 1.0 + 1e-12
    assert third_day.cash_weight >= 0.0


def test_optimizer_applies_turnover_costs_to_net_returns() -> None:
    sleeves = [
        load_sleeve_return_stream(_sleeve("sleeve-a", [0.00, 0.03, -0.02, 0.05])),
        load_sleeve_return_stream(_sleeve("sleeve-b", [0.00, -0.02, 0.04, -0.01])),
    ]

    result = optimize_strategy_portfolio(
        sleeves,
        config=PortfolioOptimizationConfig(
            lookback_days=2,
            max_strategy_weight=0.6,
            turnover_cost_bps=10.0,
        ),
    )

    for gross, net, turnover in zip(
        result.daily_gross_returns,
        result.daily_net_returns,
        result.daily_turnover,
    ):
        assert net.value == pytest.approx(gross.value - (turnover.value * 0.001))


def test_optimizer_handles_singular_covariance_with_shrinkage_and_ridge() -> None:
    sleeves = [
        load_sleeve_return_stream(_sleeve("identical-a", [0.01, 0.01, 0.01, 0.01])),
        load_sleeve_return_stream(_sleeve("identical-b", [0.01, 0.01, 0.01, 0.01])),
    ]

    result = optimize_strategy_portfolio(
        sleeves,
        config=PortfolioOptimizationConfig(
            lookback_days=3,
            max_strategy_weight=0.5,
            covariance_shrinkage=0.5,
            ridge_penalty=1e-3,
            turnover_cost_bps=0.0,
        ),
    )

    assert len(result.weight_history) == 4
    assert result.weight_history[-1].gross_weight <= 1.0 + 1e-12
    assert result.diagnostics[-1].constraint_status == "optimized"


def test_optimizer_uses_ordered_utc_day_labels_from_sleeve_artifacts() -> None:
    sleeves = [
        load_sleeve_return_stream(
            {
                "strategy_instance_id": "ordered-a",
                "strategy_id": "momentum",
                "dataset_id": "dataset-1",
                "config_fingerprint": "a",
                "daily_returns": [
                    {"label": "2026-03-01", "value": 0.01},
                    {"label": "2026-03-02", "value": 0.02},
                ],
            }
        ),
        load_sleeve_return_stream(
            {
                "strategy_instance_id": "ordered-b",
                "strategy_id": "mean_reversion",
                "dataset_id": "dataset-1",
                "config_fingerprint": "b",
                "daily_returns": [
                    {"label": "2026-03-01", "value": 0.03},
                    {"label": "2026-03-02", "value": -0.01},
                ],
            }
        ),
    ]

    result = optimize_strategy_portfolio(
        sleeves,
        config=PortfolioOptimizationConfig(lookback_days=1, turnover_cost_bps=0.0),
    )

    assert [point.label for point in result.daily_net_returns] == ["2026-03-01", "2026-03-02"]
    assert [snapshot.date for snapshot in result.weight_history] == ["2026-03-01", "2026-03-02"]


def test_load_sleeve_return_stream_validates_payload() -> None:
    with pytest.raises(ValueError, match="non-empty daily_returns"):
        load_sleeve_return_stream(
            {
                "strategy_instance_id": "bad",
                "strategy_id": "momentum",
                "dataset_id": "dataset-1",
                "config_fingerprint": "x",
                "daily_returns": [],
            }
        )
    with pytest.raises(ValueError, match="missing string field 'strategy_id'"):
        load_sleeve_return_stream(
            {
                "strategy_instance_id": "bad",
                "dataset_id": "dataset-1",
                "config_fingerprint": "x",
                "daily_returns": [{"label": "2026-03-01", "value": 0.01}],
            }
        )


def test_optimizer_rejects_misaligned_daily_dates() -> None:
    sleeve_a = load_sleeve_return_stream(_sleeve("a", [0.01, 0.02]))
    sleeve_b = load_sleeve_return_stream(
        {
            "strategy_instance_id": "b",
            "strategy_id": "momentum",
            "dataset_id": "dataset-1",
            "config_fingerprint": "b",
            "daily_returns": [
                {"label": "2026-03-01", "value": 0.01},
                {"label": "2026-03-03", "value": 0.02},
            ],
        }
    )

    with pytest.raises(ValueError, match="same ordered daily date labels"):
        optimize_strategy_portfolio([sleeve_a, sleeve_b])
