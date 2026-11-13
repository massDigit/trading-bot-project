"""Partial exits and stop protection of the exploratory DAY_02 campaign (DAY02_PARTIAL_EXITS_CAMPAIGN.md).

One economic position, sized exactly as LATE (same entry, initial stop, initial risk), split into up to
three planned portions closed at TP1, TP2 and TP3; the stop of the remaining quantity may be moved
closer, never further. Everything is fixed at the execution from values known then:

- R0 = distance from the executed price to the initial stop (the LATE risk);
- TP2 = E + I, the LATE target; TP3 = E + 2 I (2 x target - E);
- TP1 = entry + min(R0, 2/3 x (TP2 - entry)), so that TP1 always lies before TP2;
- P = TP1 + 1/2 x (TP2 - TP1), the progress towards TP2 that moves the stop to the entry price;
- quantities: thirds of the executed size in 0.1 steps, largest remainder, ties TP1 > TP3 > TP2; one
  step alone (0.1) stays a single exit at TP2; without partial exits, everything at TP2.

A level *reached* (first executable quote at or beyond it) and a portion *executed* are two different
events: a level without quantity is still reached and may move the stop. Research only: no order.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Hashable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import ROUND_FLOOR, Decimal
from itertools import pairwise

from forex_bot.risk import Side

STEP = Decimal("0.1")  # size increment of the model (ADR-035), never refined here
TP1_RISK = Decimal(1)  # TP1 at 1 x R0 ...
TP1_CAP = Decimal(2) / Decimal(3)  # ... at most 2/3 of the way to TP2
PROGRESS = Decimal(1) / Decimal(2)  # P halfway from TP1 to TP2
TP3_PROJECTION = Decimal(2)  # TP3 = E + 2 I
PORTIONS = ("TP1", "TP2", "TP3")
TIE_ORDER = ("TP1", "TP3", "TP2")  # extra steps of the largest remainder go first to TP1, then TP3
FINAL = "SOLDE"  # label of the last execution when it is not a target

# Stop moves (protection), in the order they can occur.
MOVE_BREAK_EVEN = "P atteint : stop au prix d'entrée"
MOVE_TP1 = "TP2 atteint : stop au niveau TP1"


def allocation(size: Decimal, partial: bool) -> dict[str, Decimal]:
    """Planned quantity of each portion, in 0.1 steps; the sum is always the executed size."""
    steps = int((size / STEP).to_integral_value(ROUND_FLOOR))
    if steps * STEP != size or steps < 1:
        raise ValueError(f"taille {size} hors du pas {STEP}")
    if not partial or steps == 1:
        return {"TP1": Decimal(0), "TP2": size, "TP3": Decimal(0)}
    base, extra = divmod(steps, 3)
    out = dict.fromkeys(PORTIONS, base)
    for name in TIE_ORDER[:extra]:  # equal remainders: the tie order decides
        out[name] += 1
    return {name: out[name] * STEP for name in PORTIONS}


def ahead(side: Side, price: Decimal, level: Decimal) -> bool:
    """`price` at or beyond `level` in the favourable direction."""
    return price >= level if side is Side.LONG else price <= level


def tighter(side: Side, candidate: Decimal, stop: Decimal) -> bool:
    """`candidate` strictly closer to the market than `stop` (less risk), never the opposite."""
    return candidate > stop if side is Side.LONG else candidate < stop


@dataclass
class Leg:
    """One execution of a quantity: a planned portion or the whole remaining quantity."""

    utc: datetime
    portion: str  # TP1, TP2, TP3 (planned portion) or SOLDE (remaining quantity, any other reason)
    size: Decimal
    price: Decimal
    reason: str
    stop_in_force: Decimal
    move_quote: Decimal  # USD, prices only
    lines: dict[str, Decimal]  # USD, one line per cost of this execution
    rate: Decimal  # USD -> EUR of this execution
    fee: Decimal  # EUR, conversion of this execution
    net_account: Decimal  # EUR
    financing_nights: int

    @property
    def gross_account(self) -> Decimal:
        return self.move_quote * self.rate

    @property
    def costs_account(self) -> Decimal:
        return sum(self.lines.values(), Decimal(0)) * self.rate + self.fee


@dataclass
class StopMove:
    """Decided on the quote of `utc`, in force from the next quote only (never retroactive)."""

    utc: datetime
    previous: Decimal
    stop: Decimal
    cause: str
    distance_pips: Decimal  # from the exit-side price of the deciding quote to the new stop


@dataclass
class Plan:
    """Levels and quantities fixed at the execution, then what happened to the position."""

    decided_utc: datetime
    side: Side
    size: Decimal
    entry_price: Decimal
    initial_stop: Decimal
    peak: Decimal  # E, for the independent recomputation of TP3
    r0: Decimal
    tp1: Decimal
    progress: Decimal
    tp2: Decimal
    tp3: Decimal
    quantities: dict[str, Decimal]
    protection: bool
    stop: Decimal  # in force
    reached: dict[str, datetime] = field(default_factory=dict)  # TP1, P, TP2, TP3: first quote
    executed: dict[str, datetime] = field(default_factory=dict)  # planned portions only
    legs: list[Leg] = field(default_factory=list)
    moves: list[StopMove] = field(default_factory=list)
    counterfactual: dict[str, object] | None = None  # a posteriori only, never read by a decision

    def level(self, name: str) -> Decimal:
        return {"TP1": self.tp1, "P": self.progress, "TP2": self.tp2, "TP3": self.tp3}[name]

    def pending(self) -> list[str]:
        """Planned portions with a quantity, not yet executed, in level order."""
        return [n for n in PORTIONS if self.quantities[n] > 0 and n not in self.executed]


def build_plan(
    decided_utc: datetime,
    side: Side,
    size: Decimal,
    entry_price: Decimal,
    stop: Decimal,
    peak: Decimal,
    target: Decimal,
    *,
    partial: bool,
    protection: bool,
) -> Plan | None:
    """The plan of an executed position, or None when no level lies ahead (immediate exits)."""
    sign = 1 if side is Side.LONG else -1
    r0 = sign * (entry_price - stop)
    to_tp2 = sign * (target - entry_price)
    if r0 <= 0 or to_tp2 <= 0:
        return None
    tp1 = entry_price + sign * min(TP1_RISK * r0, TP1_CAP * to_tp2)
    return Plan(
        decided_utc=decided_utc,
        side=side,
        size=size,
        entry_price=entry_price,
        initial_stop=stop,
        peak=peak,
        r0=r0,
        tp1=tp1,
        progress=tp1 + PROGRESS * (target - tp1),
        tp2=target,
        tp3=peak + TP3_PROJECTION * (target - peak),
        quantities=allocation(size, partial),
        protection=protection,
        stop=stop,
    )


# ---------------------------------------------------------------------- control and measures (reports)

STOP_PREFIX = "STOP"


def stop_in_force(plan: Plan, utc: datetime) -> Decimal:
    """Stop acting on the quote of `utc`: the last move decided on an earlier quote, else the initial."""
    stop = plan.initial_stop
    for move in plan.moves:
        if move.utc < utc:
            stop = move.stop
    return stop


def expected_levels(plan: Plan) -> tuple[Decimal, Decimal, Decimal]:
    """TP1, P and TP3 recomputed apart from `build_plan`, from the entry, the initial stop, E and TP2."""
    sign = 1 if plan.side is Side.LONG else -1
    r0 = sign * (plan.entry_price - plan.initial_stop)
    to_tp2 = sign * (plan.tp2 - plan.entry_price)
    tp1 = plan.entry_price + sign * min(r0, to_tp2 * 2 / 3)
    return tp1, tp1 + (plan.tp2 - tp1) / 2, plan.tp2 + (plan.tp2 - plan.peak)


def plan_errors(plans: list[Plan], trades: Mapping[datetime, object], partial: bool, protection: bool) -> list[str]:
    """Blocking checks: quantities conserved (planned portions apart from execution events, several
    executions on one quote allowed, a position may end before TP2 or TP3), levels, chronology, stop
    never moved further, every stop exit at the stop in force from an earlier quote (never retroactive),
    economic transaction equal to the sum of its executions."""
    errors: list[str] = []
    for plan in plans:
        key = plan.decided_utc.isoformat()
        if plan.quantities != allocation(plan.size, partial):
            errors.append(f"{key} : répartition différente de la règle")
        if sum(plan.quantities.values(), Decimal(0)) != plan.size:
            errors.append(f"{key} : quantités prévues non conservées")
        if plan.protection != protection:
            errors.append(f"{key} : protection différente de la configuration")
        tp1, progress, tp3 = expected_levels(plan)
        if max(abs(tp1 - plan.tp1), abs(progress - plan.progress), abs(tp3 - plan.tp3)) > Decimal("1e-12"):
            errors.append(f"{key} : niveaux différents du recalcul")
        sign = 1 if plan.side is Side.LONG else -1
        ordered = [plan.entry_price, plan.tp1, plan.progress, plan.tp2, plan.tp3]
        if any(sign * (b - a) <= 0 for a, b in pairwise(ordered)):
            errors.append(f"{key} : niveaux non ordonnés")
        times = [leg.utc for leg in plan.legs]
        if times != sorted(times):
            errors.append(f"{key} : exécutions non chronologiques")
        for name, executed in plan.executed.items():
            reached = plan.reached.get(name)
            if plan.quantities[name] <= 0 or reached is None or reached > executed:
                errors.append(f"{key} : {name} exécuté sans quantité ou avant d'être atteint")
        portions = [leg.portion for leg in plan.legs if leg.portion in PORTIONS]
        if len(portions) != len(set(portions)):
            errors.append(f"{key} : portion exécutée deux fois")
        for leg in plan.legs:
            if leg.portion in PORTIONS and leg.size != plan.quantities[leg.portion]:
                errors.append(f"{key} : {leg.portion} exécuté avec une autre quantité")
            if leg.portion in PORTIONS and not ahead(plan.side, leg.price, plan.level(leg.portion)):
                errors.append(f"{key} : {leg.portion} exécuté avant son niveau")
            if leg.reason.startswith(STOP_PREFIX) and leg.reason != "STOP_DÉPASSÉ_À_L'EXÉCUTION":
                if leg.stop_in_force != stop_in_force(plan, leg.utc):
                    errors.append(f"{key} : stop exécuté différent du stop en vigueur (rétroactif ?)")
        stops = [plan.initial_stop, *(m.stop for m in plan.moves)]
        if any(not tighter(plan.side, b, a) for a, b in pairwise(stops)):
            errors.append(f"{key} : stop éloigné ou déplacé sans resserrement")
        if plan.moves and not protection:
            errors.append(f"{key} : stop déplacé sans protection")
        for move in plan.moves:
            cause = "P" if move.cause == MOVE_BREAK_EVEN else "TP2"
            if plan.reached.get(cause) is None or plan.reached[cause] > move.utc:
                errors.append(f"{key} : déplacement avant son événement")
        trade = trades.get(plan.decided_utc)
        closed = trade is not None and getattr(trade, "exit_utc", None) is not None
        if closed:
            if sum((leg.size for leg in plan.legs), Decimal(0)) != plan.size:
                errors.append(f"{key} : quantités exécutées non conservées")
            if getattr(trade, "size", None) != plan.size:
                errors.append(f"{key} : transaction économique d'une autre taille")
            total = sum((leg.net_account for leg in plan.legs), Decimal(0))
            if getattr(trade, "net_account", None) != total:
                errors.append(f"{key} : net de la transaction différent de la somme des exécutions")
    return errors


def plan_view(plan: Plan) -> dict[str, object]:
    """One plan for the local session detail (levels, quantities, events, executions, moves)."""
    return {
        "r0": plan.r0,
        "levels": {"TP1": plan.tp1, "P": plan.progress, "TP2": plan.tp2, "TP3": plan.tp3},
        "quantities": plan.quantities,
        "reached": plan.reached,
        "executed": plan.executed,
        "legs": [
            {
                "utc": leg.utc,
                "portion": leg.portion,
                "size": leg.size,
                "price": leg.price,
                "reason": leg.reason,
                "stop_in_force": leg.stop_in_force,
                "gross_eur": leg.gross_account,
                "costs_eur": leg.costs_account,
                "net_eur": leg.net_account,
                "financing_nights": leg.financing_nights,
            }
            for leg in plan.legs
        ],
        "moves": [vars(m) for m in plan.moves],
        "counterfactual": plan.counterfactual,
    }


def plan_measures(plans: list[Plan]) -> dict[str, object]:
    """Quantities and results per level, remaining quantity, protection, counterfactual (a posteriori)."""
    zero = Decimal(0)
    per_portion: dict[str, dict[str, object]] = {}
    for name in PORTIONS:
        legs = [leg for p in plans for leg in p.legs if leg.portion == name]
        per_portion[name] = {
            "planned_size": sum((p.quantities[name] for p in plans), zero),
            "positions_with_quantity": sum(1 for p in plans if p.quantities[name] > 0),
            "level_reached": sum(1 for p in plans if name in p.reached),
            "reached_without_quantity": sum(1 for p in plans if name in p.reached and p.quantities[name] == 0),
            "executions": len(legs),
            "executed_size": sum((leg.size for leg in legs), zero),
            "gross_eur": sum((leg.gross_account for leg in legs), zero),
            "costs_eur": sum((leg.costs_account for leg in legs), zero),
            "net_eur": sum((leg.net_account for leg in legs), zero),
        }
    finals = [p.legs[-1] for p in plans if p.legs and p.legs[-1].portion == FINAL]

    def stage(p: Plan, leg: Leg) -> str:
        if leg.stop_in_force == p.initial_stop:
            return "stop initial"
        return "stop au prix d'entrée" if leg.stop_in_force == p.entry_price else "stop au niveau TP1"

    remaining: dict[str, dict[str, object]] = {}
    for p in plans:
        if not p.legs or p.legs[-1].portion != FINAL:
            continue
        leg = p.legs[-1]
        kind = f"{leg.reason} ({stage(p, leg)})" if leg.reason.startswith(STOP_PREFIX) else leg.reason
        row = remaining.setdefault(kind, {"n": 0, "size": zero, "net_eur": zero})
        row["n"] = int(str(row["n"])) + 1
        row["size"] = Decimal(str(row["size"])) + leg.size
        row["net_eur"] = Decimal(str(row["net_eur"])) + leg.net_account
    cf = [p.counterfactual for p in plans if p.counterfactual is not None]
    diffs = [Decimal(str(c["difference"])) for c in cf]
    avoided, cut = [d for d in diffs if d < 0], [d for d in diffs if d > 0]
    moved_exits = sum(1 for p in plans if p.legs and _moved_stop_exit(p))
    return {
        "positions": len(plans),
        "by_steps": {str(k): v for k, v in sorted(_count(int(p.size * 10) for p in plans).items())},
        "portions": per_portion,
        "progress_reached": sum(1 for p in plans if "P" in p.reached),
        "remaining_quantity_ends": remaining,
        "final_executions_of_the_remaining": len(finals),
        "execution_events_per_position": _count(len({leg.utc for leg in p.legs}) for p in plans if p.legs),
        "stop_moves": _count(m.cause for p in plans for m in p.moves),
        "stop_moves_within_5_pips_of_the_quote": sum(1 for p in plans for m in p.moves if m.distance_pips < 5),
        "remaining_closed_by_a_moved_stop": moved_exits,
        "counterfactual_initial_stop": {
            "note": "calcul a posteriori, séparé, jamais lu par une décision",
            "resolved": len(cf),
            "unresolved": moved_exits - len(cf),
            "losses_avoided": {"n": len(avoided), "eur": -sum(avoided, zero)},
            "continuations_cut_short": {"n": len(cut), "eur": sum(cut, zero)},
            "net_difference_eur": sum(diffs, zero),
        },
    }


def _moved_stop_exit(plan: Plan) -> bool:
    leg = plan.legs[-1]
    return leg.reason.startswith(STOP_PREFIX) and leg.stop_in_force != plan.initial_stop


def _count(values: Iterable[Hashable]) -> dict[Hashable, int]:
    return dict(Counter(values))
