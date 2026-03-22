import json

import pytest

from perpfut.config import RiskConfig, StrategyConfig
from perpfut.strategy_instances import (
    StrategyInstanceSpec,
    load_strategy_instance_specs,
    parse_strategy_instance_specs,
)


def test_parse_strategy_instance_specs_accepts_multiple_instances_of_same_strategy() -> None:
    specs = parse_strategy_instance_specs(
        [
            {
                "strategy_instance_id": "mom-fast-btc",
                "strategy_id": "momentum",
                "universe": ["BTC-PERP-INTX"],
                "strategy_params": {"lookback_candles": 10, "signal_scale": 20.0},
                "risk_overrides": {"max_abs_position": 0.3},
            },
            {
                "strategy_instance_id": "mom-slow-eth",
                "strategy_id": "momentum",
                "universe": ["ETH-PERP-INTX"],
                "strategy_params": {"lookback_candles": 40, "signal_scale": 55.0},
            },
        ]
    )

    assert [spec.strategy_instance_id for spec in specs] == ["mom-fast-btc", "mom-slow-eth"]
    assert [spec.strategy_id for spec in specs] == ["momentum", "momentum"]
    assert specs[0].strategy_params == {"lookback_candles": 10, "signal_scale": 20.0}
    assert specs[1].strategy_params == {"lookback_candles": 40, "signal_scale": 55.0}
    assert specs[0].risk_overrides == {"max_abs_position": 0.3}


def test_strategy_instance_spec_resolves_strategy_and_risk_configs() -> None:
    spec = StrategyInstanceSpec(
        strategy_instance_id="mr-eth",
        strategy_id="mean_reversion",
        universe=("ETH-PERP-INTX",),
        strategy_params={"lookback_candles": 12, "signal_scale": 18.5},
        risk_overrides={"max_abs_position": 0.2, "rebalance_threshold": 0.03},
    )

    strategy = spec.to_strategy_config(base=StrategyConfig())
    risk = spec.to_risk_config(base=RiskConfig())

    assert strategy.strategy_id == "mean_reversion"
    assert strategy.lookback_candles == 12
    assert strategy.signal_scale == 18.5
    assert risk.max_abs_position == 0.2
    assert risk.rebalance_threshold == 0.03
    assert risk.max_gross_position == RiskConfig().max_gross_position


def test_parse_strategy_instance_specs_rejects_duplicate_instance_ids() -> None:
    with pytest.raises(ValueError, match="duplicate strategy_instance_id 'dup'"):
        parse_strategy_instance_specs(
            [
                {
                    "strategy_instance_id": "dup",
                    "strategy_id": "momentum",
                    "universe": ["BTC-PERP-INTX"],
                },
                {
                    "strategy_instance_id": "dup",
                    "strategy_id": "mean_reversion",
                    "universe": ["ETH-PERP-INTX"],
                },
            ]
        )


def test_parse_strategy_instance_specs_rejects_unknown_param_keys() -> None:
    with pytest.raises(ValueError, match="must be one of"):
        parse_strategy_instance_specs(
            [
                {
                    "strategy_instance_id": "bad-param",
                    "strategy_id": "momentum",
                    "universe": ["BTC-PERP-INTX"],
                    "strategy_params": {"window": 5},
                }
            ]
        )


def test_parse_strategy_instance_specs_rejects_boolean_numeric_values() -> None:
    with pytest.raises(ValueError, match="must be numeric"):
        parse_strategy_instance_specs(
            [
                {
                    "strategy_instance_id": "bool-param",
                    "strategy_id": "momentum",
                    "universe": ["BTC-PERP-INTX"],
                    "strategy_params": {"lookback_candles": True},
                }
            ]
        )
    with pytest.raises(ValueError, match="must be numeric"):
        parse_strategy_instance_specs(
            [
                {
                    "strategy_instance_id": "bool-risk",
                    "strategy_id": "momentum",
                    "universe": ["BTC-PERP-INTX"],
                    "risk_overrides": {"max_abs_position": False},
                }
            ]
        )


def test_parse_strategy_instance_specs_rejects_duplicate_universe_members() -> None:
    with pytest.raises(ValueError, match="duplicate universe product 'BTC-PERP-INTX'"):
        parse_strategy_instance_specs(
            [
                {
                    "strategy_instance_id": "dupe-universe",
                    "strategy_id": "momentum",
                    "universe": ["BTC-PERP-INTX", "BTC-PERP-INTX"],
                }
            ]
        )


def test_load_strategy_instance_specs_reads_json_file(tmp_path) -> None:
    path = tmp_path / "strategy_instances.json"
    path.write_text(
        json.dumps(
            [
                {
                    "strategy_instance_id": "mom-btc",
                    "strategy_id": "momentum",
                    "universe": ["BTC-PERP-INTX"],
                    "strategy_params": {"lookback_candles": 15},
                }
            ]
        ),
        encoding="utf-8",
    )

    specs = load_strategy_instance_specs(path)

    assert len(specs) == 1
    assert specs[0].strategy_instance_id == "mom-btc"
    assert specs[0].strategy_params == {"lookback_candles": 15}
