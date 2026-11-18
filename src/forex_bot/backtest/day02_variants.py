"""Variants of the exploratory DAY_02 campaign H1-H3 (docs/experiments/DAY02_IMPROVEMENT_CAMPAIGN.md).

The frozen reference is `REF` (`Day02Params()` and its M15 comparison): its rules and results stay
reproducible. Each hypothesis has one definition, fixed before any result of the variants was read:
- H1, deferred recognition: an impulse may be recognised after its peak candle (`p < j`); amplitude
  and strong close stay on the close of j, the last closed candle at t_j; the candles after p, already
  closed, are pauses under the depth rule; nothing is dated, decided nor executed before t_j;
- H2, depth on the close: the 50 % depth invalidates on the bid close of a candle (formation, pauses,
  trigger candles), no longer on its extreme; the stop still lies beyond the flag extreme;
- H3, H4 context: an impulse is admitted only in the direction of the slope of the 20 H4 SMA (sign of
  close(k) - close(k - 20)), k the last H4 ended by the start of the impulse window.

Exit campaign (docs/experiments/DAY02_LATE_EXIT_CAMPAIGN.md), apart from H1-H3:
- LATE, longer holding: same entries, stop, target and sizing as the reference; no time exit after 2 h;
  the 17:00 London liquidation replaced by a liquidation at 22:55 Europe/Paris on the session date
  (daylight saving changes of each zone included); until then the target and the stop only.

Partial exits campaign (docs/experiments/DAY02_PARTIAL_EXITS_CAMPAIGN.md), on top of LATE unchanged:
- PROT: single exit at TP2, stop of the position protected (entry price at P, TP1 level at TP2);
- PART: TP1 / TP2 / TP3 portions, initial stop never moved;
- FULL: TP1 / TP2 / TP3 portions and the protection of the remaining quantity.
Frequency lot (docs/experiments/DAY02_FREQUENCY_CAMPAIGN.md, ADR-039), each one LATE plus one change:
- G1A: refusal at D when the peak candle is a NoWick in the direction; G5B: refusal at D when the exit
  candle opens in [07:30, 09:30) New York (a time filter, no news calendar); G1A5B: both;
- E3: limit order at E, valid 9 trigger candles, cancelled when the target is reached first;
- F2R: a Failed 2 trigger candle in the direction also confirms the exit of the flag;
- RSC: after a resume, windows may hold earlier candles, the last one starting at the resume or after;
- M5S: impulse and flag on M5, A on the M15 ATR, exit on the M5 close, 30 min of pause at most.
- SMTF: refusal at D when GBP/USD does not confirm the new EUR/USD extreme (volet C, GBP/USD candles);
- SMTT: a trigger candle where EUR/USD sweeps the flag and GBP/USD does not also confirms the exit.
Research only: nothing here sends an order.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import time, timedelta
from typing import Any

from forex_bot.backtest.day02 import Context, Day02Params, Trigger

# (H1, H2, H3, LATE, partial exits, protection) switched on, by variant.
VARIANTS: dict[str, tuple[bool, bool, bool, bool, bool, bool]] = {
    "REF": (False, False, False, False, False, False),
    "H1": (True, False, False, False, False, False),
    "H2": (False, True, False, False, False, False),
    "H3": (False, False, True, False, False, False),
    "H1H2": (True, True, False, False, False, False),
    "H1H3": (True, False, True, False, False, False),
    "H2H3": (False, True, True, False, False, False),
    "H1H2H3": (True, True, True, False, False, False),
    "LATE": (False, False, False, True, False, False),
    "PROT": (False, False, False, True, False, True),
    "PART": (False, False, False, True, True, False),
    "FULL": (False, False, False, True, True, True),
}
REFERENCE = "REF"

_LATE_EXITS: dict[str, Any] = {"time_exit": None, "liquidation": time(22, 55), "liquidation_zone": "Europe/Paris"}
# Frequency lot: name -> parameters changed from the frozen values (LATE exits always included).
FREQUENCY: dict[str, dict[str, Any]] = {
    "G1A": {"exhaustion_filter": True},
    "G5B": {"time_block_ny": (time(7, 30), time(9, 30))},
    "G1A5B": {"exhaustion_filter": True, "time_block_ny": (time(7, 30), time(9, 30))},
    "E3": {"retest_entry": True},
    "F2R": {"failed2_trigger": True},
    "RSC": {"overlap_resume": True},
    "M5S": {"unit": timedelta(minutes=5), "max_pause": timedelta(minutes=30)},
    "SMTF": {"smt_filter": True},
    "SMTT": {"smt_trigger": True},
}
ALL_VARIANTS: list[str] = [*VARIANTS, *FREQUENCY]


def variant_params(name: str, trigger: Trigger = Trigger.M5) -> Day02Params:
    """Parameters of a variant: the frozen reference values, plus the switches of its hypotheses."""
    if name in FREQUENCY:
        return replace(Day02Params(trigger=trigger), **_LATE_EXITS, **FREQUENCY[name])
    if name not in VARIANTS:
        raise ValueError(f"variante inconnue : {name}")
    h1, h2, h3, late, partial, protection = VARIANTS[name]
    params = replace(
        Day02Params(trigger=trigger),
        deferred_recognition=h1,
        depth_on_close=h2,
        context=Context.H4_SMA_SLOPE if h3 else Context.NONE,
    )
    if late:
        params = replace(params, time_exit=None, liquidation=time(22, 55), liquidation_zone="Europe/Paris")
    return replace(params, partial_exits=partial, protection=protection)


def variant_of(params: Day02Params) -> str:
    """Name of the variant whose switches `params` carries (the trigger aside)."""
    for name in ALL_VARIANTS:
        if variant_params(name, params.trigger) == params:
            return name
    raise ValueError("paramètres hors des variantes enregistrées")


def needs_m15_atr(name: str) -> bool:
    """M5S: A is read on the M15 ATR (the M15 candles take the place of the H1)."""
    return variant_params(name).unit == timedelta(minutes=5)


def needs_smt(name: str) -> bool:
    """SMTF and SMTT read the GBP/USD candles."""
    params = variant_params(name)
    return params.smt_filter or params.smt_trigger


def needs_h4(name: str) -> bool:
    return variant_params(name).context is not Context.NONE
