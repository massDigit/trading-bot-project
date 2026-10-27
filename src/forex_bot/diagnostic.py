"""Read-only connection diagnostic for the IG demo API.

Run with:  uv run ig-demo-diagnostic

Exit codes:
    0  every check passed
    1  local configuration error (nothing was sent to IG)
    2  blocking failure (network, authentication, accounts)
    3  partial result (connected, but the market or its constraints are incomplete)
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TextIO

import httpx

from forex_bot.config import IG_DEMO_BASE_URL, ConfigError, Settings, load_settings
from forex_bot.ig_client import IGApiError, IGDemoReadOnlyClient, ReadOnlyViolation
from forex_bot.redaction import Redactor

EXIT_OK = 0
EXIT_CONFIG = 1
EXIT_BLOCKING = 2
EXIT_PARTIAL = 3

MAX_MARKET_DETAILS = 5
NOT_PROVIDED = "non fourni par l'API"

# Explanations for errorCode values documented in the IG Labs reference.
ERROR_HINTS: dict[str, str] = {
    "error.security.invalid-details": (
        "Identifiant ou mot de passe refusé. Vérifier qu'il s'agit bien des identifiants "
        "du compte DÉMO (ils diffèrent de ceux du compte réel)."
    ),
    "error.security.api-key-missing": "Clé API absente de la requête (IG_API_KEY vide ?).",
    "error.security.api-key-invalid": (
        "Clé API inconnue. Vérifier qu'elle a été générée depuis le compte démo "
        "(My Account > API keys sur la plateforme démo)."
    ),
    "error.security.api-key-disabled": "Clé API désactivée : la réactiver dans My Account.",
    "error.security.api-key-revoked": "Clé API révoquée : en générer une nouvelle.",
    "error.security.api-key-restricted": "Clé API restreinte pour cette opération.",
    "error.security.invalid-application": "Application/clé API non valide pour ce compte.",
    "error.security.too-many-failed-attempts": (
        "Trop d'échecs de connexion : compte temporairement bloqué. Attendre avant de réessayer."
    ),
    "error.security.account-suspended": "Compte suspendu côté IG.",
    "error.security.client-suspended": "Client suspendu côté IG.",
    "error.security.account-not-yet-activated": "Compte démo pas encore activé.",
    "error.public-api.failure.encryption.required": (
        "IG exige un mot de passe chiffré pour ce compte (POST /session/encryptionKey). "
        "Non implémenté dans ce premier diagnostic : à ajouter si ce blocage apparaît."
    ),
    "error.public-api.failure.pending.agreements.required": (
        "Des conditions d'utilisation sont à accepter : se connecter une fois à la "
        "plateforme web démo et valider les écrans proposés."
    ),
    "error.public-api.failure.kyc.required": "Vérification d'identité (KYC) requise par IG.",
    "error.public-api.failure.preferred.account.not.set": (
        "Aucun compte par défaut défini : en choisir un sur la plateforme web démo."
    ),
    "error.public-api.failure.preferred.account.disabled": "Le compte par défaut est désactivé.",
    "error.public-api.exceeded-api-key-allowance": "Quota de la clé API dépassé : réessayer plus tard.",
    "error.public-api.exceeded-account-allowance": "Quota du compte dépassé : réessayer plus tard.",
    "endpoint.unavailable.for.api-key": "Endpoint non disponible pour cette clé API.",
    "error.security.authentication.timeout": "Délai d'authentification dépassé côté IG.",
    "invalid.input": "Requête jugée invalide par IG.",
}


@dataclass
class Check:
    name: str
    status: str  # "OK" | "AVERTISSEMENT" | "ÉCHEC" | "NON EXÉCUTÉ"
    detail: str = ""


@dataclass
class Report:
    checks: list[Check] = field(default_factory=list)

    def add(self, name: str, status: str, detail: str = "") -> None:
        self.checks.append(Check(name, status, detail))

    def exit_code(self) -> int:
        failed = {c.name for c in self.checks if c.status == "ÉCHEC"}
        if CHECK_CONFIG in failed:
            return EXIT_CONFIG
        if failed & BLOCKING_CHECKS:
            return EXIT_BLOCKING
        statuses = {c.status for c in self.checks}
        if statuses & {"ÉCHEC", "AVERTISSEMENT", "NON EXÉCUTÉ"}:
            return EXIT_PARTIAL
        return EXIT_OK


CHECK_CONFIG = "Configuration locale"
CHECK_AUTH = "Authentification (POST /session)"
CHECK_ACCOUNTS = "Comptes accessibles (GET /accounts)"
CHECK_BALANCE = "Solde du compte sélectionné"
CHECK_SEARCH = "Recherche du marché"
CHECK_RULES = "Contraintes du marché (GET /markets/{epic})"
CHECK_LOGOUT = "Fermeture de session (DELETE /session)"
BLOCKING_CHECKS = {CHECK_AUTH, CHECK_ACCOUNTS}


def explain(exc: Exception) -> str:
    if isinstance(exc, IGApiError):
        hint = ERROR_HINTS.get(exc.error_code or "", "")
        text = f"HTTP {exc.status_code}, errorCode={exc.error_code or 'absent'}"
        return f"{text}. {hint}" if hint else text
    if isinstance(exc, httpx.TimeoutException):
        return "Délai réseau dépassé en contactant demo-api.ig.com."
    if isinstance(exc, httpx.ConnectError):
        return "Connexion impossible à demo-api.ig.com (réseau, DNS, proxy ou pare-feu)."
    if isinstance(exc, httpx.HTTPError):
        return f"Erreur réseau : {type(exc).__name__}."
    return f"{type(exc).__name__}: {exc}"


def fmt_rule(rule: Any) -> str:
    """Format an IG dealing rule object {unit, value}."""
    if not isinstance(rule, dict) or rule.get("value") is None:
        return NOT_PROVIDED
    unit = rule.get("unit")
    return f"{rule['value']} {unit}" if unit else str(rule["value"])


def fmt(value: Any) -> str:
    return NOT_PROVIDED if value is None or value == "" else str(value)


def select_spot_candidates(markets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep currency markets without expiry ('-' in IG search results)."""
    return [m for m in markets if m.get("instrumentType") == "CURRENCIES" and m.get("expiry") in ("-", None, "")]


def run(
    settings_loader: Callable[[], Settings] = load_settings,
    transport: httpx.BaseTransport | None = None,
    stream: TextIO = sys.stdout,
) -> int:
    redactor = Redactor()
    report = Report()

    def out(line: str = "") -> None:
        stream.write(redactor.mask(line) + "\n")

    out("=== Diagnostic IG — démo, lecture seule ===")
    out(f"URL verrouillée : {IG_DEMO_BASE_URL}")
    out("Aucun ordre, aucune modification de position, aucun accès au compte réel.")
    out("")

    try:
        settings = settings_loader()
    except ConfigError as exc:
        report.add(CHECK_CONFIG, "ÉCHEC", str(exc))
        return _finish(report, out)
    redactor.register_many(settings.secrets())
    report.add(CHECK_CONFIG, "OK", f"terme de recherche : {settings.search_term}")

    client = IGDemoReadOnlyClient(settings.api_key, redactor, transport=transport)
    try:
        _diagnose(client, settings, redactor, report, out)
    except ReadOnlyViolation as exc:  # programming error: must never happen
        report.add("Garde lecture seule", "ÉCHEC", str(exc))
    finally:
        had_session = client.has_session
        client.close()
        if client.logout_error is not None:
            report.add(CHECK_LOGOUT, "AVERTISSEMENT", explain(client.logout_error))
        elif had_session:
            report.add(CHECK_LOGOUT, "OK")

    return _finish(report, out)


def _diagnose(
    client: IGDemoReadOnlyClient,
    settings: Settings,
    redactor: Redactor,
    report: Report,
    out: Callable[[str], None],
) -> None:
    # 1. Authentication -------------------------------------------------------
    out("--- 1. Authentification")
    try:
        session = client.login(settings.username, settings.password)
    except (IGApiError, httpx.HTTPError) as exc:
        report.add(CHECK_AUTH, "ÉCHEC", explain(exc))
        for name in (CHECK_ACCOUNTS, CHECK_BALANCE, CHECK_SEARCH, CHECK_RULES):
            report.add(name, "NON EXÉCUTÉ", "authentification requise")
        out("Échec.")
        return

    current_id = str(session.get("currentAccountId") or "")
    redactor.register("ACCOUNT_ID", current_id)
    redactor.register("CLIENT_ID", str(session.get("clientId") or ""))
    for acc in session.get("accounts") or []:
        redactor.register("ACCOUNT_ID", str(acc.get("accountId") or ""))
    report.add(CHECK_AUTH, "OK", "jetons CST et X-SECURITY-TOKEN reçus (masqués)")
    out("Session ouverte (jetons reçus, non affichés).")
    out(f"Devise du client : {fmt(session.get('currencyIsoCode'))}")
    out(f"Trading autorisé sur la session (dealingEnabled) : {fmt(session.get('dealingEnabled'))}")
    out("")

    # 2. Accounts --------------------------------------------------------------
    out("--- 2. Comptes accessibles")
    try:
        accounts = client.get_accounts()
    except (IGApiError, httpx.HTTPError) as exc:
        report.add(CHECK_ACCOUNTS, "ÉCHEC", explain(exc))
        report.add(CHECK_BALANCE, "NON EXÉCUTÉ", "liste des comptes indisponible")
        accounts = []
    else:
        report.add(CHECK_ACCOUNTS, "OK", f"{len(accounts)} compte(s)")

    aliases: dict[str, str] = {}
    for index, acc in enumerate(accounts, start=1):
        acc_id = str(acc.get("accountId") or "")
        alias = f"Compte #{index}"
        aliases[acc_id] = alias
        redactor.register(alias.upper().replace(" #", "_"), acc_id)
        markers = []
        if acc_id == current_id:
            markers.append("actif")
        if acc.get("preferred"):
            markers.append("par défaut")
        out(
            f"{alias} : type={fmt(acc.get('accountType'))}, nom={fmt(acc.get('accountName'))}, "
            f"devise={fmt(acc.get('currency'))}, statut={fmt(acc.get('status'))}"
            + (f" [{', '.join(markers)}]" if markers else "")
        )
    out("")

    # 3. Selected account balance ---------------------------------------------
    if accounts:
        out("--- 3. Compte sélectionné")
        _show_balance(client, settings, accounts, aliases, current_id, report, out)
        out("")
    elif not any(c.name == CHECK_BALANCE for c in report.checks):
        report.add(CHECK_BALANCE, "ÉCHEC", "aucun compte accessible")

    # 4. Market search ---------------------------------------------------------
    out(f"--- 4. Recherche « {settings.search_term} »")
    try:
        markets = client.search_markets(settings.search_term)
    except (IGApiError, httpx.HTTPError) as exc:
        report.add(CHECK_SEARCH, "ÉCHEC", explain(exc))
        report.add(CHECK_RULES, "NON EXÉCUTÉ", "recherche indisponible")
        return

    for m in markets:
        out(
            f"  {fmt(m.get('epic'))} | {fmt(m.get('instrumentName'))} | "
            f"type={fmt(m.get('instrumentType'))} | échéance={fmt(m.get('expiry'))} | "
            f"statut={fmt(m.get('marketStatus'))} | bid={fmt(m.get('bid'))} offer={fmt(m.get('offer'))}"
        )
    candidates = select_spot_candidates(markets)
    if not candidates:
        report.add(
            CHECK_SEARCH,
            "ÉCHEC",
            f"{len(markets)} résultat(s), aucun marché CURRENCIES sans échéance",
        )
        report.add(CHECK_RULES, "NON EXÉCUTÉ", "aucun marché candidat")
        return
    report.add(
        CHECK_SEARCH,
        "OK",
        f"{len(markets)} résultat(s), {len(candidates)} marché(s) devise sans échéance",
    )
    out("")

    # 5. Market constraints ----------------------------------------------------
    out("--- 5. Contraintes des marchés candidats")
    missing_any = False
    detailed = 0
    for m in candidates[:MAX_MARKET_DETAILS]:
        epic = str(m.get("epic") or "")
        try:
            details = client.get_market(epic)
        except (IGApiError, httpx.HTTPError, ValueError) as exc:
            out(f"[{epic}] échec : {explain(exc)}")
            missing_any = True
            continue
        detailed += 1
        missing_any |= _show_market(details, out)
        out("")
    if len(candidates) > MAX_MARKET_DETAILS:
        out(f"({len(candidates) - MAX_MARKET_DETAILS} candidat(s) non détaillé(s), quota API préservé)")

    if detailed == 0:
        report.add(CHECK_RULES, "ÉCHEC", "aucun détail de marché obtenu")
    elif missing_any:
        report.add(CHECK_RULES, "AVERTISSEMENT", "certaines contraintes ne sont pas fournies")
    else:
        report.add(CHECK_RULES, "OK", f"{detailed} marché(s) détaillé(s)")


def _show_balance(
    client: IGDemoReadOnlyClient,
    settings: Settings,
    accounts: list[dict[str, Any]],
    aliases: dict[str, str],
    current_id: str,
    report: Report,
    out: Callable[[str], None],
) -> None:
    target_id = settings.account_id or current_id
    selected = next((a for a in accounts if str(a.get("accountId")) == target_id), None)
    if selected is None:
        report.add(CHECK_BALANCE, "ÉCHEC", "IG_ACCOUNT_ID ne correspond à aucun compte accessible")
        return

    if target_id != current_id:
        try:
            client.switch_account(target_id)  # default account left unchanged
        except (IGApiError, httpx.HTTPError) as exc:
            report.add(CHECK_BALANCE, "ÉCHEC", f"bascule de compte impossible : {explain(exc)}")
            return
        out(f"Session basculée sur {aliases[target_id]} (compte par défaut inchangé).")

    balance = selected.get("balance") or {}
    currency = fmt(selected.get("currency"))
    out(f"{aliases[target_id]} ({fmt(selected.get('accountType'))}), devise {currency} — montants fictifs :")
    out(f"  balance    : {fmt(balance.get('balance'))}")
    out(f"  available  : {fmt(balance.get('available'))}")
    out(f"  deposit    : {fmt(balance.get('deposit'))}")
    out(f"  profitLoss : {fmt(balance.get('profitLoss'))}")
    if balance.get("balance") is None:
        report.add(CHECK_BALANCE, "AVERTISSEMENT", "solde non fourni")
    else:
        report.add(CHECK_BALANCE, "OK", f"{aliases[target_id]}, {balance.get('balance')} {currency}")


def _show_market(details: dict[str, Any], out: Callable[[str], None]) -> bool:
    """Print constraints of one market. Returns True if a key constraint is missing."""
    instrument = details.get("instrument") or {}
    rules = details.get("dealingRules") or {}
    snapshot = details.get("snapshot") or {}

    currencies = instrument.get("currencies") or []
    codes = ", ".join(f"{c.get('code')}{' (défaut)' if c.get('isDefault') else ''}" for c in currencies)
    margin_unit = instrument.get("marginFactorUnit") or ""

    rows: list[tuple[str, str]] = [
        ("type / unité", f"{fmt(instrument.get('type'))} / {fmt(instrument.get('unit'))}"),
        (
            "statut / bid / offer",
            f"{fmt(snapshot.get('marketStatus'))} / {fmt(snapshot.get('bid'))} / {fmt(snapshot.get('offer'))}",
        ),
        (
            "lotSize / contractSize",
            f"{fmt(instrument.get('lotSize'))} / {fmt(instrument.get('contractSize'))}",
        ),
        ("onePipMeans", fmt(instrument.get("onePipMeans"))),
        ("valueOfOnePip", fmt(instrument.get("valueOfOnePip"))),
        ("devises de cotation", codes or NOT_PROVIDED),
        ("marginFactor", f"{fmt(instrument.get('marginFactor'))} {margin_unit}".rstrip()),
        ("taille minimale (minDealSize)", fmt_rule(rules.get("minDealSize"))),
        ("minStepDistance", fmt_rule(rules.get("minStepDistance"))),
        (
            "stop normal min (minNormalStopOrLimitDistance)",
            fmt_rule(rules.get("minNormalStopOrLimitDistance")),
        ),
        (
            "stop garanti min (minControlledRiskStopDistance)",
            fmt_rule(rules.get("minControlledRiskStopDistance")),
        ),
        ("stop/limite max (maxStopOrLimitDistance)", fmt_rule(rules.get("maxStopOrLimitDistance"))),
        ("controlledRiskSpacing", fmt_rule(rules.get("controlledRiskSpacing"))),
        (
            "marketOrderPreference / trailingStops",
            f"{fmt(rules.get('marketOrderPreference'))} / {fmt(rules.get('trailingStopsPreference'))}",
        ),
        (
            "stopsLimitsAllowed / forceOpenAllowed",
            f"{fmt(instrument.get('stopsLimitsAllowed'))} / {fmt(instrument.get('forceOpenAllowed'))}",
        ),
    ]
    out(f"[{fmt(instrument.get('epic'))}] {fmt(instrument.get('name'))}")
    width = max(len(label) for label, _ in rows)
    for label, value in rows:
        out(f"  {label.ljust(width)} : {value}")
    out("  Incrément de taille : l'API ne documente pas de champ dédié. minStepDistance est")
    out("    décrit seulement comme « Dealing rule » ; son interprétation reste à confirmer.")

    key_rules = ("minDealSize", "minNormalStopOrLimitDistance")
    return any(fmt_rule(rules.get(k)) == NOT_PROVIDED for k in key_rules)


def _finish(report: Report, out: Callable[[str], None]) -> int:
    out("")
    out("=== Synthèse ===")
    for check in report.checks:
        out(f"[{check.status}] {check.name}" + (f" — {check.detail}" if check.detail else ""))
    code = report.exit_code()
    verdict = {
        EXIT_OK: "Diagnostic réussi.",
        EXIT_CONFIG: "Configuration locale incomplète.",
        EXIT_BLOCKING: "Blocage : voir les lignes ÉCHEC ci-dessus.",
        EXIT_PARTIAL: "Connexion établie, résultat partiel : voir les avertissements.",
    }[code]
    out(f"Code de sortie {code} : {verdict}")
    return code


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
