"""Shared simulated IG responses."""

from __future__ import annotations

from typing import Any

# Values observed on the IG demo on 2026-10-27 for CS.D.EURUSD.CEFM.IP.
MARKET_DETAILS: dict[str, Any] = {
    "instrument": {
        "epic": "CS.D.EURUSD.CEFM.IP",
        "name": "EUR/USD Mini",
        "expiry": "-",
        "type": "CURRENCIES",
        "unit": "CONTRACTS",
        "lotSize": 1.0,
        "contractSize": "10000",
        "onePipMeans": "0.0001 USD/EUR",
        "valueOfOnePip": "1.00",
        "currencies": [{"code": "USD", "isDefault": False}],
        "marginFactor": 3.33,
        "marginFactorUnit": "PERCENTAGE",
        "stopsLimitsAllowed": True,
        "forceOpenAllowed": True,
    },
    "dealingRules": {
        "minDealSize": {"unit": "POINTS", "value": 0.1},
        "minStepDistance": {"unit": "POINTS", "value": 5.0},
        "minNormalStopOrLimitDistance": {"unit": "POINTS", "value": 2.0},
        "minControlledRiskStopDistance": {"unit": "POINTS", "value": 5.0},
        "maxStopOrLimitDistance": {"unit": "PERCENTAGE", "value": 75.0},
        "controlledRiskSpacing": {"unit": "POINTS", "value": 20.0},
        "marketOrderPreference": "AVAILABLE_DEFAULT_OFF",
        "trailingStopsPreference": "AVAILABLE",
    },
    "snapshot": {"marketStatus": "TRADEABLE", "bid": 1.11498, "offer": 1.11508},
}
