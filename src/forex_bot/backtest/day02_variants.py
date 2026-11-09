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
Research only: nothing here sends an order.
"""

from __future__ import annotations

from dataclasses import replace

from forex_bot.backtest.day02 import Context, Day02Params, Trigger

# (H1, H2, H3) switched on, by variant.
VARIANTS: dict[str, tuple[bool, bool, bool]] = {
    "REF": (False, False, False),
    "H1": (True, False, False),
    "H2": (False, True, False),
    "H3": (False, False, True),
    "H1H2": (True, True, False),
    "H1H3": (True, False, True),
    "H2H3": (False, True, True),
    "H1H2H3": (True, True, True),
}
REFERENCE = "REF"


def variant_params(name: str, trigger: Trigger = Trigger.M5) -> Day02Params:
    """Parameters of a variant: the frozen reference values, plus the switches of its hypotheses."""
    if name not in VARIANTS:
        raise ValueError(f"variante inconnue : {name}")
    h1, h2, h3 = VARIANTS[name]
    return replace(
        Day02Params(trigger=trigger),
        deferred_recognition=h1,
        depth_on_close=h2,
        context=Context.H4_SMA_SLOPE if h3 else Context.NONE,
    )


def variant_of(params: Day02Params) -> str:
    """Name of the variant whose switches `params` carries (the trigger aside)."""
    for name in VARIANTS:
        if variant_params(name, params.trigger) == params:
            return name
    raise ValueError("paramètres hors des variantes enregistrées")


def needs_h4(name: str) -> bool:
    return variant_params(name).context is not Context.NONE
