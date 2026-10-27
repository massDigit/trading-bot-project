"""Estimated loss at stop and position sizing (cahier des charges §8, §9).

Price convention (explicit, see ASSUMP-008)
-------------------------------------------
- `bid` is the price at which we sell, `offer` the price at which we buy.
- Entry estimate: LONG buys at the current offer, SHORT sells at the current bid.
- The stop level is expressed on the EXIT side: a LONG stop is a bid level (we
  sell to exit), a SHORT stop is an offer level (we buy to exit).
- Price loss per base unit at stop:
      LONG  = offer_entry - stop   (+ slippage provision)
      SHORT = stop - bid_entry     (+ slippage provision)
  The spread is therefore counted exactly ONCE, through the entry on the
  unfavourable side. No separate spread term is added.
- A LONG stop must be strictly below the current bid, a SHORT stop strictly
  above the current offer (otherwise it would trigger immediately).

Other principles
----------------
- The technical stop is NEVER moved: the size is reduced (rounded down) or the
  signal is refused.
- Costs are CONFIRMED, ASSUMED or UNKNOWN. An UNKNOWN cost is never replaced by
  zero: it is listed as excluded from the estimate and blocks executable sizing.
- The risk budget is computed on the up-to-date equity of the portfolio
  allocated to the robot, not on the initial allocation (2 000 EUR) nor on the
  broker balance. Without that equity, sizing is blocked.
- Results are ESTIMATES of the loss at stop, never a guaranteed maximum loss.

All amounts use Decimal. Nothing in this module talks to the broker.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import ROUND_DOWN, Decimal
from enum import StrEnum

from forex_bot.instruments import BrokerConventions, ContractCheck, ContractSpec
from forex_bot.market import DEFAULT_MAX_QUOTE_AGE, Quote, quote_blockers

ESTIMATE_NOTICE = (
    "Perte ESTIMÉE au stop, hors gaps, glissement supérieur à la provision, rejet ou panne : "
    "ce n'est pas une perte maximale garantie."
)


class Side(StrEnum):
    LONG = "LONG"
    SHORT = "SHORT"


class Holding(StrEnum):
    INTRADAY = "INTRADAY"  # closed before the end of the session, no financing
    OVERNIGHT = "OVERNIGHT"  # swing: financing applies for each night held


class CostStatus(StrEnum):
    CONFIRMED = "CONFIRMED"  # from an authoritative broker source
    ASSUMED = "ASSUMED"  # project hypothesis, listed in .ai/ASSUMPTIONS.md
    UNKNOWN = "UNKNOWN"  # not known: never treated as zero


@dataclass(frozen=True)
class Cost:
    status: CostStatus
    value: Decimal | None
    source: str

    def __post_init__(self) -> None:
        if (self.status is CostStatus.UNKNOWN) != (self.value is None):
            raise ValueError("Un coût UNKNOWN n'a pas de valeur ; un coût connu ou supposé en a une.")
        if self.value is not None and self.value < 0:
            raise ValueError("Une provision de coût ne peut pas être négative.")


@dataclass(frozen=True)
class CostModel:
    """Cost provisions. Amounts in quote currency (USD) per contract unless stated."""

    slippage_pips: Cost = Cost(CostStatus.ASSUMED, Decimal("0.5"), "ASSUMP-006")
    commission_per_contract: Cost = Cost(CostStatus.UNKNOWN, None, "grille IG à vérifier")
    financing_per_contract_per_night: Cost = Cost(CostStatus.UNKNOWN, None, "financement overnight IG à vérifier")
    conversion_fee_rate: Cost = Cost(
        CostStatus.UNKNOWN, None, "frais de conversion USD->EUR IG à vérifier"
    )  # fraction of the amount
    guaranteed_stop_premium_per_contract: Cost = Cost(CostStatus.UNKNOWN, None, "prime de stop garanti IG à vérifier")


@dataclass(frozen=True)
class PortfolioEquity:
    """Up-to-date equity of the portfolio allocated to the robot (realised, unrealised, fees, flows)."""

    value: Decimal
    currency: str
    as_of_utc: datetime
    source: str


@dataclass(frozen=True)
class RiskConfig:
    """§8 proposals, not approved for live trading."""

    initial_allocation: Decimal = Decimal("2000")  # starting capital, NOT the sizing base
    account_currency: str = "EUR"
    risk_fraction_per_trade: Decimal = Decimal("0.0025")  # 0,25 % of up-to-date equity
    max_equity_age: timedelta = timedelta(minutes=5)  # ASSUMP-010
    max_quote_age: timedelta = DEFAULT_MAX_QUOTE_AGE  # ASSUMP-009


@dataclass(frozen=True)
class ConversionRate:
    """Amount of `to_currency` for 1 unit of `from_currency`, on the conservative side."""

    from_currency: str
    to_currency: str
    rate: Decimal


def usd_to_eur_from_eurusd_bid(bid: Decimal) -> ConversionRate:
    """1 / EUR/USD bid: the bid is the lower price, so the EUR amount of a USD loss is the larger."""
    return ConversionRate("USD", "EUR", Decimal(1) / bid)


@dataclass(frozen=True)
class LossEstimate:
    """Estimated loss at stop for ONE contract (`ContractSpec.contract_size` base units)."""

    entry_estimate: Decimal
    stop_price: Decimal
    price_loss: Decimal  # per base unit, spread included once, slippage included if known
    stop_distance_pips: Decimal  # from the current exit-side price to the stop
    loss_quote_per_contract: Decimal
    loss_account_per_contract: Decimal
    included: tuple[str, ...]  # "name (STATUS)"
    excluded_unknown: tuple[str, ...]  # applicable costs NOT included because unknown

    @property
    def complete(self) -> bool:
        return not self.excluded_unknown


class SizingStatus(StrEnum):
    SIZED = "SIZED"
    BLOCKED = "BLOCKED"
    REJECTED_INVALID_INPUT = "REJECTED_INVALID_INPUT"
    REJECTED_STOP_BELOW_BROKER_MINIMUM = "REJECTED_STOP_BELOW_BROKER_MINIMUM"
    REJECTED_MIN_SIZE_EXCEEDS_BUDGET = "REJECTED_MIN_SIZE_EXCEEDS_BUDGET"


@dataclass(frozen=True)
class SizingResult:
    status: SizingStatus
    reasons: tuple[str, ...]
    side: Side
    stop_price: Decimal  # always the input stop, never adjusted
    estimate: LossEstimate | None = None
    budget: Decimal | None = None  # on up-to-date equity; None if unavailable
    indicative_budget_on_initial_allocation: Decimal | None = None  # information only
    executable_size: Decimal | None = None  # deal-size units, only when SIZED
    estimated_loss_at_stop: Decimal | None = None  # account currency, only when SIZED
    notice: str = field(default=ESTIMATE_NOTICE)


def applicable_costs(costs: CostModel, holding: Holding, guaranteed_stop: bool) -> dict[str, Cost]:
    applicable = {
        "glissement": costs.slippage_pips,
        "commission": costs.commission_per_contract,
        "conversion de devise": costs.conversion_fee_rate,
    }
    if holding is Holding.OVERNIGHT:
        applicable["financement overnight"] = costs.financing_per_contract_per_night
    if guaranteed_stop:
        applicable["prime de stop garanti"] = costs.guaranteed_stop_premium_per_contract
    return applicable


def estimate_loss_per_contract(
    *,
    side: Side,
    stop_price: Decimal,
    quote: Quote,
    spec: ContractSpec,
    conversion: ConversionRate,
    costs: CostModel,
    holding: Holding,
    nights: int = 0,
    guaranteed_stop: bool = False,
) -> LossEstimate:
    """Estimated loss at stop for one contract. Raises ValueError on invalid inputs."""
    if quote.bid <= 0 or quote.offer < quote.bid or stop_price <= 0:
        raise ValueError("prix ou cotation invalides")
    if conversion.from_currency != spec.quote_currency or conversion.rate <= 0:
        raise ValueError(f"conversion attendue depuis {spec.quote_currency}, taux positif")
    if holding is Holding.OVERNIGHT and nights < 1:
        raise ValueError("une détention overnight exige au moins une nuit")
    if holding is Holding.INTRADAY and nights != 0:
        raise ValueError("une détention intrajournalière n'a pas de nuit")

    if side is Side.LONG:
        if stop_price >= quote.bid:
            raise ValueError("stop d'achat au niveau ou au-dessus du bid courant")
        entry = quote.offer
        price_loss = entry - stop_price
        exit_side_distance = quote.bid - stop_price
    else:
        if stop_price <= quote.offer:
            raise ValueError("stop de vente au niveau ou en dessous de l'offer courant")
        entry = quote.bid
        price_loss = stop_price - entry
        exit_side_distance = stop_price - quote.offer

    included = ["spread, via le prix d'entrée (CONFIRMED : cotation)"]
    excluded: list[str] = []
    applicable = applicable_costs(costs, holding, guaranteed_stop)

    def known(name: str) -> Decimal | None:
        cost = applicable[name]
        if cost.value is None:
            excluded.append(f"{name} ({cost.source})")
            return None
        included.append(f"{name} ({cost.status})")
        return cost.value

    slippage = known("glissement")
    if slippage is not None:
        price_loss += slippage * spec.pip_size
    loss_quote = price_loss * spec.contract_size
    for name in ("commission", "prime de stop garanti"):
        if name in applicable and (value := known(name)) is not None:
            loss_quote += value
    if "financement overnight" in applicable and (value := known("financement overnight")) is not None:
        loss_quote += value * nights
    loss_account = loss_quote * conversion.rate
    if (fee := known("conversion de devise")) is not None:
        loss_account *= 1 + fee

    return LossEstimate(
        entry_estimate=entry,
        stop_price=stop_price,
        price_loss=price_loss,
        stop_distance_pips=exit_side_distance / spec.pip_size,
        loss_quote_per_contract=loss_quote,
        loss_account_per_contract=loss_account,
        included=tuple(included),
        excluded_unknown=tuple(excluded),
    )


def equity_blockers(equity: PortfolioEquity | None, risk: RiskConfig, now_utc: datetime) -> list[str]:
    if equity is None:
        return ["fonds propres actualisés du portefeuille du robot indisponibles"]
    blockers = []
    if equity.currency != risk.account_currency:
        blockers.append(f"fonds propres en {equity.currency}, attendu {risk.account_currency}")
    if equity.value <= 0:
        blockers.append("fonds propres nuls ou négatifs")
    if now_utc - equity.as_of_utc > risk.max_equity_age:
        blockers.append("fonds propres périmés")
    return blockers


def entry_blockers(
    *,
    quote: Quote | None,
    now_utc: datetime,
    contract_check: ContractCheck | None,
    conventions: BrokerConventions,
    equity: PortfolioEquity | None,
    costs: CostModel,
    holding: Holding,
    guaranteed_stop: bool,
    risk: RiskConfig,
) -> list[str]:
    """Every reason that currently forbids a future entry. Empty list = entry may be sized."""
    blockers = ["cotation indisponible"] if quote is None else quote_blockers(quote, now_utc, risk.max_quote_age)
    if contract_check is None:
        blockers.append("contrat non vérifié")
    elif not contract_check.characteristics_ok:
        blockers.append("caractéristiques du contrat différentes de la référence")
    blockers += equity_blockers(equity, risk, now_utc)
    blockers += [f"convention non confirmée : {name}" for name in conventions.missing()]
    blockers += [
        f"coût inconnu : {name} ({cost.source})"
        for name, cost in applicable_costs(costs, holding, guaranteed_stop).items()
        if cost.status is CostStatus.UNKNOWN
    ]
    return blockers


def size_position(
    *,
    side: Side,
    stop_price: Decimal,
    quote: Quote,
    now_utc: datetime,
    spec: ContractSpec,
    contract_check: ContractCheck | None,
    conventions: BrokerConventions,
    conversion: ConversionRate,
    equity: PortfolioEquity | None,
    holding: Holding,
    nights: int = 0,
    guaranteed_stop: bool = False,
    costs: CostModel | None = None,
    risk: RiskConfig | None = None,
) -> SizingResult:
    """Size a future entry. Produces an executable size only if nothing is blocked."""
    costs = costs or CostModel()
    risk = risk or RiskConfig()
    indicative_budget = risk.initial_allocation * risk.risk_fraction_per_trade

    def result(
        status: SizingStatus,
        reasons: list[str],
        estimate: LossEstimate | None = None,
        budget: Decimal | None = None,
        executable_size: Decimal | None = None,
        estimated_loss_at_stop: Decimal | None = None,
    ) -> SizingResult:
        return SizingResult(
            status=status,
            reasons=tuple(reasons),
            side=side,
            stop_price=stop_price,
            estimate=estimate,
            budget=budget,
            indicative_budget_on_initial_allocation=indicative_budget,
            executable_size=executable_size,
            estimated_loss_at_stop=estimated_loss_at_stop,
        )

    if conversion.to_currency != risk.account_currency:
        return result(SizingStatus.REJECTED_INVALID_INPUT, [f"conversion vers {risk.account_currency} attendue"])
    try:
        estimate = estimate_loss_per_contract(
            side=side,
            stop_price=stop_price,
            quote=quote,
            spec=spec,
            conversion=conversion,
            costs=costs,
            holding=holding,
            nights=nights,
            guaranteed_stop=guaranteed_stop,
        )
    except ValueError as exc:
        return result(SizingStatus.REJECTED_INVALID_INPUT, [str(exc)])

    # Broker minimum stop distance: refuse, never move the stop. Only checkable
    # once the IG point / pip ratio is confirmed.
    if conventions.points_per_pip is not None:
        stop_points = estimate.stop_distance_pips * conventions.points_per_pip
        if stop_points < spec.min_normal_stop_raw_points:
            return result(
                SizingStatus.REJECTED_STOP_BELOW_BROKER_MINIMUM,
                [f"stop à {stop_points} points < minimum courtier {spec.min_normal_stop_raw_points}"],
                estimate=estimate,
            )

    blockers = entry_blockers(
        quote=quote,
        now_utc=now_utc,
        contract_check=contract_check,
        conventions=conventions,
        equity=equity,
        costs=costs,
        holding=holding,
        guaranteed_stop=guaranteed_stop,
        risk=risk,
    )

    budget = equity.value * risk.risk_fraction_per_trade if equity is not None and equity.value > 0 else None
    if blockers:
        return result(SizingStatus.BLOCKED, blockers, estimate=estimate, budget=budget)

    # Everything confirmed: these asserts only narrow types for mypy.
    if (
        budget is None
        or conventions.contracts_per_size_unit is None
        or conventions.min_size is None
        or conventions.size_increment is None
    ):
        raise RuntimeError("état incohérent : aucun blocage mais données manquantes")

    loss_per_size_unit = estimate.loss_account_per_contract * conventions.contracts_per_size_unit
    steps = (budget / loss_per_size_unit / conventions.size_increment).to_integral_value(rounding=ROUND_DOWN)
    size = steps * conventions.size_increment
    if size < conventions.min_size:
        return result(
            SizingStatus.REJECTED_MIN_SIZE_EXCEEDS_BUDGET,
            [
                f"taille minimale {conventions.min_size} : perte estimée "
                f"{conventions.min_size * loss_per_size_unit:.2f} {risk.account_currency} > budget {budget:.2f}"
            ],
            estimate=estimate,
            budget=budget,
        )
    return result(
        SizingStatus.SIZED,
        ["taille arrondie à l'incrément inférieur ; perte au stop estimée, non garantie"],
        estimate=estimate,
        budget=budget,
        executable_size=size,
        estimated_loss_at_stop=size * loss_per_size_unit,
    )
