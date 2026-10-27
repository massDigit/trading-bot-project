"""Explicit instrument selection, unit conventions and contract verification.

V1 trades (later) a single, explicitly chosen contract: IG EUR/USD Mini
`CS.D.EURUSD.CEFM.IP`. It is never picked from a search result, and the
"Weekend EUR/USD" market (`IX.D.SUNEURUSD.CEF.IP`) is explicitly excluded.

Units used in this project
--------------------------
- price      : EUR/USD quote, in USD per 1 EUR (e.g. 1.11498).
- pip        : 0.0001 in price. Source: `instrument.onePipMeans` = "0.0001 USD/EUR" (API field).
- contract   : `instrument.contractSize` = 10 000 EUR of base currency (API field).
               Value of 1 pip for 1 contract = 0.0001 x 10 000 = 1 USD, consistent with
               `instrument.valueOfOnePip` = "1.00" (checked by `verify_contract`).
- IG point   : unit of `dealingRules` distances ("POINTS"). Its ratio to the pip is NOT
               confirmed -> `BrokerConventions.points_per_pip` is None.
- size unit  : unit of the deal size (`minDealSize` is reported with unit "POINTS"). Its
               ratio to the contract is NOT confirmed -> `contracts_per_size_unit` is None.

Unconfirmed conventions are left empty (None). Code depending on them must block,
never substitute a default value. A convention can only be set through a
`Confirmation` carrying its source, its date and the epic it applies to.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any

EURUSD_MINI_EPIC = "CS.D.EURUSD.CEFM.IP"
EXCLUDED_EPICS = frozenset({"IX.D.SUNEURUSD.CEF.IP"})  # Weekend EUR/USD
EXCLUDED_NAME_MARKERS = ("weekend",)

TRADEABLE = "TRADEABLE"


@dataclass(frozen=True)
class ContractSpec:
    """Reference characteristics, observed on the IG demo on 2026-10-27 (GET /markets/{epic} v3)."""

    epic: str
    instrument_type: str
    expiry: str
    contract_size: Decimal  # base-currency units per contract (contractSize)
    one_pip_means: str
    pip_size: Decimal  # price move of one pip (parsed from onePipMeans)
    value_of_one_pip: Decimal  # valueOfOnePip, quote currency, for 1 contract
    base_currency: str
    quote_currency: str
    min_deal_size_raw: Decimal  # minDealSize value as returned; unit NOT confirmed
    min_normal_stop_raw_points: Decimal  # minNormalStopOrLimitDistance value, in IG points
    min_guaranteed_stop_raw_points: Decimal  # minControlledRiskStopDistance value, in IG points


EURUSD_MINI = ContractSpec(
    epic=EURUSD_MINI_EPIC,
    instrument_type="CURRENCIES",
    expiry="-",
    contract_size=Decimal("10000"),
    one_pip_means="0.0001 USD/EUR",
    pip_size=Decimal("0.0001"),
    value_of_one_pip=Decimal("1.00"),
    base_currency="EUR",
    quote_currency="USD",
    min_deal_size_raw=Decimal("0.1"),
    min_normal_stop_raw_points=Decimal("2.0"),
    min_guaranteed_stop_raw_points=Decimal("5.0"),
)


@dataclass(frozen=True)
class Confirmation[T]:
    """A broker convention confirmed by an identified source, for one contract.

    `source` names the document or support answer (never "déduction"), `confirmed_on`
    its date. A confirmation for another epic is ignored.
    """

    value: T
    source: str
    confirmed_on: date
    epic: str

    def __post_init__(self) -> None:
        if not self.source.strip():
            raise ValueError("Une confirmation exige une source.")


class StopTriggerSide(StrEnum):
    # LONG stop triggered by the bid, SHORT stop by the offer (the convention implemented in risk.py)
    EXIT_SIDE = "EXIT_SIDE"
    # LONG stop triggered by the offer, SHORT stop by the bid
    ENTRY_SIDE = "ENTRY_SIDE"
    MID = "MID"


class DistanceReference(StrEnum):
    """Price from which IG measures a minimum stop distance."""

    EXIT_SIDE = "EXIT_SIDE"  # bid for a LONG, offer for a SHORT
    ENTRY_SIDE = "ENTRY_SIDE"  # offer for a LONG, bid for a SHORT
    MID = "MID"


IMPLEMENTED_STOP_TRIGGER_SIDE = StopTriggerSide.EXIT_SIDE

_DECIMAL_CONVENTIONS = ("points_per_pip", "contracts_per_size_unit", "min_size", "size_increment")


@dataclass(frozen=True)
class BrokerConventions:
    """Broker conventions. None = not confirmed.

    A value may be set only from IG documentation/support or a separately
    authorised demo test, never from an inference of this code.
    """

    points_per_pip: Confirmation[Decimal] | None = None  # IG distance points in one pip
    contracts_per_size_unit: Confirmation[Decimal] | None = None  # contracts in one deal-size unit
    min_size: Confirmation[Decimal] | None = None  # in deal-size units
    size_increment: Confirmation[Decimal] | None = None  # in deal-size units
    stop_trigger_side: Confirmation[StopTriggerSide] | None = None  # ASSUMP-008
    normal_stop_distance_reference: Confirmation[DistanceReference] | None = None  # ASSUMP-008
    guaranteed_stop_distance_reference: Confirmation[DistanceReference] | None = None  # ASSUMP-008

    def get[T](self, confirmation: Confirmation[T] | None, epic: str) -> T | None:
        """Confirmed value for this epic, else None."""
        if confirmation is None or confirmation.epic != epic:
            return None
        return confirmation.value

    def decimal(self, name: str, epic: str) -> Decimal | None:
        value = self.get(getattr(self, name), epic)
        return value if isinstance(value, Decimal) and value > 0 else None

    def missing(self, epic: str, guaranteed_stop: bool = False) -> list[str]:
        """Conventions needed for a sized entry on `epic` that are not confirmed for it."""
        names = [n for n in _DECIMAL_CONVENTIONS if self.decimal(n, epic) is None]
        if self.get(self.stop_trigger_side, epic) is None:
            names.append("stop_trigger_side")
        reference = "guaranteed_stop_distance_reference" if guaranteed_stop else "normal_stop_distance_reference"
        if self.get(getattr(self, reference), epic) is None:
            names.append(reference)
        return names


# Nothing confirmed as of 2026-10-27 (ASSUMP-004, ASSUMP-005, ASSUMP-008).
EURUSD_MINI_CONVENTIONS = BrokerConventions()


CONTRACT_CHECK_SOURCE = "REST GET /markets/{epic} v3"


@dataclass
class ContractCheck:
    """Result of `verify_contract`. Usable only if both flags are true.

    Provenance: REST market details. `market_status` is `snapshot.marketStatus`;
    `checked_at_utc` is the LOCAL receipt time of the response (v3 gives no
    usable IG timestamp), None if unknown.
    """

    characteristics_ok: bool
    tradeable_now: bool
    issues: list[str] = field(default_factory=list)
    market_status: str | None = None
    checked_at_utc: datetime | None = None
    source: str = CONTRACT_CHECK_SOURCE

    @property
    def usable(self) -> bool:
        return self.characteristics_ok and self.tradeable_now


def is_excluded_market(epic: str, name: str | None) -> bool:
    lowered = (name or "").lower()
    return epic in EXCLUDED_EPICS or any(marker in lowered for marker in EXCLUDED_NAME_MARKERS)


def to_decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value).strip())
    except InvalidOperation:
        return None


def pip_size_from_one_pip_means(text: Any) -> Decimal | None:
    """'0.0001 USD/EUR' -> Decimal('0.0001'); None if not parseable."""
    if not isinstance(text, str) or not text.strip():
        return None
    return to_decimal(text.split()[0])


def verify_contract(
    details: dict[str, Any], spec: ContractSpec = EURUSD_MINI, received_at_utc: datetime | None = None
) -> ContractCheck:
    """Compare a GET /markets/{epic} v3 response, received at `received_at_utc`, with the reference contract."""
    instrument = details.get("instrument") or {}
    rules = details.get("dealingRules") or {}
    snapshot = details.get("snapshot") or {}
    issues: list[str] = []

    def expect(label: str, observed: Any, expected: Any) -> None:
        if observed != expected:
            issues.append(f"{label} : attendu {expected}, observé {observed}")

    epic = str(instrument.get("epic") or "")
    name = instrument.get("name")
    expect("epic", epic, spec.epic)
    if is_excluded_market(epic, name):
        issues.append(f"marché exclu : {name}")
    expect("type", instrument.get("type"), spec.instrument_type)
    expect("expiry", instrument.get("expiry"), spec.expiry)
    contract_size = to_decimal(instrument.get("contractSize"))
    expect("contractSize", contract_size, spec.contract_size)
    expect("onePipMeans", instrument.get("onePipMeans"), spec.one_pip_means)
    pip_size = pip_size_from_one_pip_means(instrument.get("onePipMeans"))
    expect("taille du pip", pip_size, spec.pip_size)
    value_of_one_pip = to_decimal(instrument.get("valueOfOnePip"))
    expect("valueOfOnePip", value_of_one_pip, spec.value_of_one_pip)
    # Internal consistency: pip size x contract size must equal the value of one pip.
    if pip_size is not None and contract_size is not None and value_of_one_pip is not None:
        if pip_size * contract_size != value_of_one_pip:
            issues.append(f"incohérence : pip {pip_size} x contrat {contract_size} != valueOfOnePip {value_of_one_pip}")
    codes = {c.get("code") for c in instrument.get("currencies") or []}
    if spec.quote_currency not in codes:
        issues.append(f"devise de cotation {spec.quote_currency} absente (observé : {sorted(map(str, codes))})")
    expect("stopsLimitsAllowed", instrument.get("stopsLimitsAllowed"), True)
    expect("minDealSize", to_decimal((rules.get("minDealSize") or {}).get("value")), spec.min_deal_size_raw)
    expect(
        "minNormalStopOrLimitDistance",
        to_decimal((rules.get("minNormalStopOrLimitDistance") or {}).get("value")),
        spec.min_normal_stop_raw_points,
    )
    expect(
        "unité minNormalStopOrLimitDistance", (rules.get("minNormalStopOrLimitDistance") or {}).get("unit"), "POINTS"
    )
    expect(
        "minControlledRiskStopDistance",
        to_decimal((rules.get("minControlledRiskStopDistance") or {}).get("value")),
        spec.min_guaranteed_stop_raw_points,
    )
    expect(
        "unité minControlledRiskStopDistance", (rules.get("minControlledRiskStopDistance") or {}).get("unit"), "POINTS"
    )
    characteristics_ok = not issues

    status = snapshot.get("marketStatus")
    bid, offer = to_decimal(snapshot.get("bid")), to_decimal(snapshot.get("offer"))
    tradeable = status == TRADEABLE
    if not tradeable:
        issues.append(f"marché non négociable : {status}")
    if bid is None or offer is None or bid <= 0 or offer < bid:
        issues.append(f"cotation incohérente : bid={bid}, offer={offer}")
        tradeable = False

    return ContractCheck(
        characteristics_ok=characteristics_ok,
        tradeable_now=tradeable,
        issues=issues,
        market_status=status,
        checked_at_utc=received_at_utc,
    )
