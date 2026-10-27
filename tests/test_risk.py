"""Price convention, units, costs, equity and entry gate.

Expected values are computed by hand in the comments. Quote used throughout:
bid 1.11498 / offer 1.11508 -> spread 0.00010 (1 pip).
"""

from __future__ import annotations

import copy
import inspect
from datetime import UTC, datetime, timedelta
from decimal import Decimal as D

import pytest
from ig_fixtures import MARKET_DETAILS

from forex_bot.instruments import (
    EURUSD_MINI,
    EURUSD_MINI_CONVENTIONS,
    BrokerConventions,
    ContractCheck,
    is_excluded_market,
    pip_size_from_one_pip_means,
    verify_contract,
)
from forex_bot.market import Quote, quote_blockers, quote_from_market_details
from forex_bot.risk import (
    ESTIMATE_NOTICE,
    ConversionRate,
    Cost,
    CostModel,
    CostStatus,
    Holding,
    LossEstimate,
    PortfolioEquity,
    Side,
    SizingResult,
    SizingStatus,
    estimate_loss_per_contract,
    size_position,
    usd_to_eur_from_eurusd_bid,
)

NOW = datetime(2026, 10, 27, 12, 0, 0, tzinfo=UTC)
BID, OFFER = D("1.11498"), D("1.11508")
QUOTE = Quote(BID, OFFER, "TRADEABLE", NOW - timedelta(seconds=1))
USD_EUR = usd_to_eur_from_eurusd_bid(BID)
CHECK_OK = ContractCheck(characteristics_ok=True, tradeable_now=True)
EQUITY_2000 = PortfolioEquity(D("2000"), "EUR", NOW - timedelta(minutes=1), "test")

# ---- TEST-ONLY values. They are NOT confirmed IG values; they only exercise the arithmetic.
TEST_CONVENTIONS = BrokerConventions(
    points_per_pip=D("1"), contracts_per_size_unit=D("1"), min_size=D("0.1"), size_increment=D("0.1")
)
TEST_COSTS = CostModel(
    slippage_pips=Cost(CostStatus.ASSUMED, D("0.5"), "test"),
    commission_per_contract=Cost(CostStatus.CONFIRMED, D("0"), "test"),
    financing_per_contract_per_night=Cost(CostStatus.CONFIRMED, D("0.30"), "test"),
    conversion_fee_rate=Cost(CostStatus.CONFIRMED, D("0"), "test"),
    guaranteed_stop_premium_per_contract=Cost(CostStatus.CONFIRMED, D("3"), "test"),
)


def estimate(
    side: Side,
    stop: str,
    *,
    quote: Quote = QUOTE,
    costs: CostModel = TEST_COSTS,
    holding: Holding = Holding.INTRADAY,
    nights: int = 0,
    guaranteed_stop: bool = False,
) -> LossEstimate:
    return estimate_loss_per_contract(
        side=side,
        stop_price=D(stop),
        quote=quote,
        spec=EURUSD_MINI,
        conversion=USD_EUR,
        costs=costs,
        holding=holding,
        nights=nights,
        guaranteed_stop=guaranteed_stop,
    )


def size(
    side: Side,
    stop: str,
    *,
    quote: Quote = QUOTE,
    conventions: BrokerConventions = TEST_CONVENTIONS,
    costs: CostModel = TEST_COSTS,
    equity: PortfolioEquity | None = EQUITY_2000,
    check: ContractCheck | None = CHECK_OK,
    conversion: ConversionRate = USD_EUR,
) -> SizingResult:
    return size_position(
        side=side,
        stop_price=D(stop),
        quote=quote,
        now_utc=NOW,
        spec=EURUSD_MINI,
        contract_check=check,
        conventions=conventions,
        conversion=conversion,
        equity=equity,
        holding=Holding.INTRADAY,
        costs=costs,
    )


# ---------------------------------------------------------------- 1. price convention


def test_long_entry_at_offer_stop_on_bid_side() -> None:
    # entry = offer 1.11508 ; stop 1.11200 (bid level)
    # price loss = 1.11508 - 1.11200 = 0.00308 ; + slippage 0.5 pip = 0.00005 -> 0.00313
    # per contract: 0.00313 x 10 000 = 31.30 USD ; / 1.11498 = 28.0723 EUR
    e = estimate(Side.LONG, "1.11200")
    assert e.entry_estimate == OFFER
    assert e.price_loss == D("0.00313")
    assert e.loss_quote_per_contract == D("31.30")
    assert round(e.loss_account_per_contract, 4) == D("28.0723")
    assert e.stop_distance_pips == D("29.8")  # (1.11498 - 1.11200) / 0.0001


def test_short_entry_at_bid_stop_on_offer_side() -> None:
    # entry = bid 1.11498 ; stop 1.11800 (offer level)
    # price loss = 1.11800 - 1.11498 = 0.00302 ; + 0.00005 -> 0.00307
    # per contract: 30.70 USD ; / 1.11498 = 27.5341 EUR
    e = estimate(Side.SHORT, "1.11800")
    assert e.entry_estimate == BID
    assert e.price_loss == D("0.00307")
    assert e.loss_quote_per_contract == D("30.70")
    assert round(e.loss_account_per_contract, 4) == D("27.5341")
    assert e.stop_distance_pips == D("29.2")  # (1.11800 - 1.11508) / 0.0001


@pytest.mark.parametrize(("side", "stop"), [(Side.LONG, "1.11200"), (Side.SHORT, "1.11800")])
def test_spread_is_counted_exactly_once(side: Side, stop: str) -> None:
    # Same stop; zero-spread quote at the exit-side price vs the 1-pip spread quote.
    # The difference must be exactly one spread: 0.0001 x 10 000 = 1.00 USD.
    exit_price = BID if side is Side.LONG else OFFER
    no_spread = Quote(exit_price, exit_price, "TRADEABLE", QUOTE.quote_time_utc)
    with_spread = estimate(side, stop).loss_quote_per_contract
    assert with_spread - estimate(side, stop, quote=no_spread).loss_quote_per_contract == D("1.00")


@pytest.mark.parametrize(
    ("side", "stop"),
    [(Side.LONG, "1.11498"), (Side.LONG, "1.11600"), (Side.SHORT, "1.11508"), (Side.SHORT, "1.11400")],
)
def test_stop_on_wrong_side_of_exit_price_is_invalid(side: Side, stop: str) -> None:
    assert size(side, stop).status is SizingStatus.REJECTED_INVALID_INPUT


def test_conversion_uses_conservative_bid() -> None:
    assert USD_EUR.rate == D(1) / BID
    assert USD_EUR.rate > D(1) / OFFER  # larger EUR amount for a USD loss


def test_wrong_conversion_target_is_invalid() -> None:
    r = size(Side.LONG, "1.11200", conversion=ConversionRate("USD", "GBP", D("0.8")))
    assert r.status is SizingStatus.REJECTED_INVALID_INPUT


# ---------------------------------------------------------------- 2. units


def test_pip_and_contract_units_from_api_fields() -> None:
    pip = pip_size_from_one_pip_means("0.0001 USD/EUR")
    assert pip == D("0.0001")
    assert pip * EURUSD_MINI.contract_size == EURUSD_MINI.value_of_one_pip  # 1.00 USD per pip per contract
    assert estimate(Side.LONG, "1.11198").stop_distance_pips == D("30")  # 0.0030 in price = 30 pips


def test_unconfirmed_conventions_are_none_and_block() -> None:
    assert EURUSD_MINI_CONVENTIONS.missing() == [
        "points_per_pip",
        "contracts_per_size_unit",
        "min_size",
        "size_increment",
    ]
    r = size(Side.LONG, "1.11200", conventions=EURUSD_MINI_CONVENTIONS)
    assert r.status is SizingStatus.BLOCKED
    assert r.executable_size is None
    for name in EURUSD_MINI_CONVENTIONS.missing():
        assert f"convention non confirmée : {name}" in r.reasons


def test_min_stop_check_needs_confirmed_points() -> None:
    stop = "1.11483"  # 1.5 pip below the bid
    # points/pip unknown: NOT silently assumed 1:1 -> cannot be checked, stays blocked
    r = size(Side.LONG, stop, conventions=EURUSD_MINI_CONVENTIONS)
    assert r.status is SizingStatus.BLOCKED
    assert "convention non confirmée : points_per_pip" in r.reasons
    # with a test-only ratio of 1 point per pip: 1.5 < 2 -> refused, stop untouched
    r = size(Side.LONG, stop)
    assert r.status is SizingStatus.REJECTED_STOP_BELOW_BROKER_MINIMUM
    assert r.stop_price == D(stop)


def test_value_of_one_pip_inconsistency_is_detected() -> None:
    bad = copy.deepcopy(MARKET_DETAILS)
    bad["instrument"]["valueOfOnePip"] = "10.00"
    check = verify_contract(bad)
    assert not check.characteristics_ok
    assert any("incohérence" in i for i in check.issues)


# ---------------------------------------------------------------- 3. costs


def test_cost_invariants() -> None:
    with pytest.raises(ValueError):
        Cost(CostStatus.UNKNOWN, D("0"), "x")
    with pytest.raises(ValueError):
        Cost(CostStatus.CONFIRMED, None, "x")
    with pytest.raises(ValueError):
        Cost(CostStatus.ASSUMED, D("-1"), "x")


def test_unknown_costs_are_excluded_not_zero_and_block() -> None:
    e = estimate(Side.LONG, "1.11200", costs=CostModel())
    assert not e.complete
    assert any(x.startswith("commission") for x in e.excluded_unknown)
    assert any(x.startswith("conversion de devise") for x in e.excluded_unknown)
    assert not any(x.startswith("financement") for x in e.excluded_unknown)  # intraday: not applicable
    r = size(Side.LONG, "1.11200", costs=CostModel())
    assert r.status is SizingStatus.BLOCKED
    assert any(reason.startswith("coût inconnu : commission") for reason in r.reasons)


def test_swing_financing_per_night() -> None:
    # 3 nights x 0.30 USD = 0.90 USD: 31.30 + 0.90 = 32.20 USD
    e = estimate(Side.LONG, "1.11200", holding=Holding.OVERNIGHT, nights=3)
    assert e.loss_quote_per_contract == D("32.20")
    unknown_fin = estimate(Side.LONG, "1.11200", costs=CostModel(), holding=Holding.OVERNIGHT, nights=3)
    assert any(x.startswith("financement overnight") for x in unknown_fin.excluded_unknown)
    with pytest.raises(ValueError):
        estimate(Side.LONG, "1.11200", holding=Holding.OVERNIGHT, nights=0)


def test_guaranteed_stop_premium_and_conversion_fee() -> None:
    # premium 3 USD: 31.30 + 3 = 34.30 USD
    assert estimate(Side.LONG, "1.11200", guaranteed_stop=True).loss_quote_per_contract == D("34.30")
    unknown_premium = estimate(Side.LONG, "1.11200", costs=CostModel(), guaranteed_stop=True)
    assert any(x.startswith("prime de stop garanti") for x in unknown_premium.excluded_unknown)
    # conversion fee 0.5 %: 28.072253 x 1.005 = 28.212614 -> 28.2126 EUR
    with_fee = CostModel(
        slippage_pips=TEST_COSTS.slippage_pips,
        commission_per_contract=TEST_COSTS.commission_per_contract,
        conversion_fee_rate=Cost(CostStatus.CONFIRMED, D("0.005"), "test"),
    )
    assert round(estimate(Side.LONG, "1.11200", costs=with_fee).loss_account_per_contract, 4) == D("28.2126")


# ---------------------------------------------------------------- 4. estimate, not guarantee


def test_sized_result_is_an_estimate() -> None:
    # budget = 2 000 x 0.25 % = 5.00 ; 5 / 28.0723 = 0.178 -> 0.1 ; estimated loss 2.81 EUR
    r = size(Side.LONG, "1.11200")
    assert r.status is SizingStatus.SIZED
    assert r.executable_size == D("0.1")
    assert r.estimated_loss_at_stop is not None and round(r.estimated_loss_at_stop, 2) == D("2.81")
    assert r.notice == ESTIMATE_NOTICE
    assert "pas une perte maximale garantie" in r.notice
    assert any("estimée, non garantie" in reason for reason in r.reasons)


@pytest.mark.parametrize("pips", [3, 10, 25, 40, 55, 70, 150, 400])
def test_stop_never_moved(pips: int) -> None:
    stop = BID - D(pips) * D("0.0001")
    r = size(Side.LONG, str(stop))
    assert r.stop_price == stop
    if r.status is SizingStatus.SIZED:
        assert r.budget is not None and r.estimated_loss_at_stop is not None
        assert r.estimated_loss_at_stop <= r.budget
    else:
        assert r.status is SizingStatus.REJECTED_MIN_SIZE_EXCEEDS_BUDGET
        assert r.executable_size is None


def test_wide_stop_refused_not_tightened() -> None:
    # 1.11508 - 1.10700 = 0.00808 + 0.00005 = 0.00813 -> 81.30 USD -> 72.92 EUR ; 0.1 -> 7.29 > 5
    r = size(Side.LONG, "1.10700")
    assert r.status is SizingStatus.REJECTED_MIN_SIZE_EXCEEDS_BUDGET
    assert r.stop_price == D("1.10700")


# ---------------------------------------------------------------- 5. equity vs initial allocation


def test_no_equity_tracking_blocks_sizing() -> None:
    r = size(Side.LONG, "1.11200", equity=None)
    assert r.status is SizingStatus.BLOCKED
    assert "fonds propres actualisés du portefeuille du robot indisponibles" in r.reasons
    assert r.budget is None
    assert r.indicative_budget_on_initial_allocation == D("5.0000")


def test_budget_follows_up_to_date_equity_not_initial_allocation() -> None:
    # equity 4 000 -> budget 10 ; 10 / 28.0723 = 0.356 -> 0.3
    r = size(Side.LONG, "1.11200", equity=PortfolioEquity(D("4000"), "EUR", NOW, "test"))
    assert r.budget == D("10.0000")
    assert r.executable_size == D("0.3")
    assert "balance" not in inspect.signature(size_position).parameters


@pytest.mark.parametrize(
    ("equity", "reason"),
    [
        (PortfolioEquity(D("2000"), "EUR", NOW - timedelta(minutes=10), "t"), "fonds propres périmés"),
        (PortfolioEquity(D("2000"), "USD", NOW, "t"), "fonds propres en USD, attendu EUR"),
        (PortfolioEquity(D("0"), "EUR", NOW, "t"), "fonds propres nuls ou négatifs"),
    ],
)
def test_invalid_equity_blocks(equity: PortfolioEquity, reason: str) -> None:
    r = size(Side.LONG, "1.11200", equity=equity)
    assert r.status is SizingStatus.BLOCKED
    assert reason in r.reasons


# ---------------------------------------------------------------- 6. closed market, stale quote


@pytest.mark.parametrize(
    ("quote", "reason"),
    [
        (Quote(BID, OFFER, "CLOSED", NOW), "marché non négociable (CLOSED)"),
        (Quote(BID, OFFER, "EDITS_ONLY", NOW), "marché non négociable (EDITS_ONLY)"),
        (Quote(BID, OFFER, "TRADEABLE", None), "horodatage de la cotation inconnu"),
        (Quote(BID, OFFER, "TRADEABLE", NOW - timedelta(seconds=30)), "cotation périmée (30 s > 10 s)"),
        (Quote(BID, OFFER, "TRADEABLE", NOW + timedelta(seconds=10)), "horodatage de la cotation dans le futur"),
        (Quote(BID, OFFER, "TRADEABLE", datetime(2026, 10, 27, 12, 0)), "horodatage de la cotation sans fuseau"),
    ],
)
def test_closed_market_or_stale_quote_blocks_entry(quote: Quote, reason: str) -> None:
    assert reason in quote_blockers(quote, NOW)
    r = size(Side.LONG, "1.11200", quote=quote)
    assert r.status is SizingStatus.BLOCKED
    assert reason in r.reasons
    assert r.executable_size is None


def test_fresh_tradeable_quote_has_no_blocker() -> None:
    assert quote_blockers(QUOTE, NOW) == []
    with pytest.raises(ValueError):
        quote_blockers(QUOTE, datetime(2026, 10, 27, 12, 0))


def test_v3_snapshot_time_is_not_converted() -> None:
    quote = quote_from_market_details(MARKET_DETAILS)
    assert quote is not None and quote.quote_time_utc is None
    assert "horodatage de la cotation inconnu" in quote_blockers(quote, NOW)


# ---------------------------------------------------------------- contract selection


def test_unverified_or_drifted_contract_blocks() -> None:
    assert "contrat non vérifié" in size(Side.LONG, "1.11200", check=None).reasons
    drifted = ContractCheck(characteristics_ok=False, tradeable_now=True)
    reasons = size(Side.LONG, "1.11200", check=drifted).reasons
    assert "caractéristiques du contrat différentes de la référence" in reasons


def test_observed_mini_contract_is_valid_and_tradeable() -> None:
    check = verify_contract(MARKET_DETAILS)
    assert check.issues == []
    assert check.usable


def test_weekend_market_is_excluded() -> None:
    assert is_excluded_market("IX.D.SUNEURUSD.CEF.IP", "Weekend EUR/USD")
    assert is_excluded_market("ANY", "Weekend EUR/USD")
    assert not is_excluded_market("CS.D.EURUSD.CEFM.IP", "EUR/USD Mini")
    weekend = copy.deepcopy(MARKET_DETAILS)
    weekend["instrument"].update(epic="IX.D.SUNEURUSD.CEF.IP", name="Weekend EUR/USD", onePipMeans="1 Index Point")
    assert not verify_contract(weekend).usable
