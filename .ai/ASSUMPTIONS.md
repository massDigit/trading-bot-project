# ASSUMPTIONS.md - Hypothèses & Propositions à Valider

> **Ce fichier isole les hypothèses techniques et propositions émises par l'IA en attente de confirmation explicite par l'utilisateur.**

---

## ⚠️ Classification & Règles

Tout élément figurant ici est une **PROPOSITION** et ne doit pas être considéré comme une contrainte d'architecture définitive tant qu'il n'a pas été validé par l'utilisateur.

Chaque entrée précise sa **nature**, car elle détermine ce qui peut la valider :

| Nature | Exemple | Ce qui la valide |
|---|---|---|
| `CHOIX DU PROJET` | version de Python, seuil expérimental, convention de bougies | l'approbation de l'opérateur |
| `FAIT EXTÉRIEUR` | unité IG, tarif, fermeture historique, format d'un fournisseur | une **preuve applicable** (documentation officielle, confirmation écrite), consignée dans `docs/CONFIRMATIONS.md` ; l'approbation de l'opérateur ne suffit pas |
| `OBSERVATION` | valeur vue sur la démo, comportement du SDK | rien : c'est un constat daté, jamais généralisé au réel |

Une entrée peut mêler plusieurs natures : chacune est alors traitée séparément. Une hypothèse de
recherche ne devient jamais silencieusement une règle d'exécution réelle.

### Format d'une hypothèse / proposition :
- **ID** : `ASSUMP-001`
- **Sujet** : [ex: Choix du SGBD / Stratégie d'authentification]
- **Nature** : `CHOIX DU PROJET` | `FAIT EXTÉRIEUR` | `OBSERVATION`
- **Proposition** : [ex: PostgreSQL + Prisma ORM]
- **Raisonnement** : [Pourquoi cette solution est suggérée]
- **Statut** : `PROPOSED` | `UNDER_REVIEW` | `APPROVED` | `REJECTED` | `SUPERSEDED`

Une proposition `APPROVED` est consignée dans `.ai/DECISIONS.md` avec sa date, sa portée et sa source.

---

## 📋 Hypothèses et Propositions Actives

- **ID** : `ASSUMP-001`
- **Sujet** : Version de Python et outil d'environnement
- **Nature** : `CHOIX DU PROJET`
- **Proposition** : Python 3.12 arm64 géré par `uv` (`.python-version`, `uv.lock`), au lieu du Python 3.14 Homebrew.
- **Raisonnement** : environnement isolé et reproductible. La compatibilité des futurs outils d'IA sera vérifiée lorsqu'ils seront réellement ajoutés.
- **Statut** : `APPROVED` (2026-10-30, ADR-008) — Python 3.12 et uv pour le projet actuel

- **ID** : `ASSUMP-002`
- **Sujet** : Client HTTP et authentification IG
- **Nature** : `CHOIX DU PROJET`
- **Proposition** : `httpx` ; `POST /session` version 2 (jetons `CST` / `X-SECURITY-TOKEN`) pour le **diagnostic** lecture seule.
- **Raisonnement** : la v2 renvoie directement comptes et compte actif. Ne s'étend pas au fonctionnement continu, qui devra gérer l'expiration de session sans compter sur une durée fixe.
- **Statut** : `APPROVED` (2026-10-30, ADR-008) — pour le diagnostic seulement ; pas pour le fonctionnement continu

- **ID** : `ASSUMP-003`
- **Sujet** : Sélection du marché EUR/USD
- **Nature** : `CHOIX DU PROJET`
- **Proposition** : la recherche dynamique des contrats EUR/USD (`instrumentType = CURRENCIES`, sans échéance) reste un **outil de diagnostic**. Le contrat utilisé est sélectionné explicitement (Mini, `CS.D.EURUSD.CEFM.IP`, ADR-003).
- **Raisonnement** : la proposition initiale (ne pas figer d'epic) est dépassée par la sélection explicite du contrat Mini.
- **Statut** : `SUPERSEDED` (2026-10-30) par ADR-003 ; recherche dynamique conservée comme outil de diagnostic

- **ID** : `ASSUMP-004`
- **Sujet** : Incrément de taille des positions
- **Nature** : `CHOIX DU PROJET` (précaution) + `FAIT EXTÉRIEUR` (valeur)
- **Proposition** : ne pas interpréter `dealingRules.minStepDistance` comme l'incrément de taille sans preuve applicable. La valeur de l'incrément reste inconnue.
- **Raisonnement** : le point décisif est l'absence de définition applicable : la référence IG ne documente aucun champ d'incrément de taille et décrit `minStepDistance` seulement comme « Dealing rule ». L'écart observé entre `minDealSize` = 0,1 et `minStepDistance` = 5,0 (démo, 2026-10-27) n'est pas une démonstration.
- **Statut** : `APPROVED` (2026-10-30, ADR-008) pour la **précaution** ; la valeur de l'incrément reste un fait extérieur inconnu

- **ID** : `ASSUMP-005`
- **Sujet** : Unités IG pour EUR/USD Mini
- **Nature** : `FAIT EXTÉRIEUR` (à décomposer) + `OBSERVATION`
- **Proposition** : traiter séparément cinq questions : unité de transaction (`instrument.unit`), unité de `contractSize`, rapport point / pip, taille minimale, incrément. Les observations de la démo sont établies (`docs/CONFIRMATIONS.md` §1-2) ; leurs interprétations ne le sont pas toutes. Aucune n'est supposée implicitement (pas de 1 point = 1 pip, pas de 1 unité = 1 contrat) ; les vérifications qui en dépendent restent bloquées.
- **Statut** : `PROPOSED` — fait extérieur, ouvert : en attente d'une preuve applicable (non approuvable)

- **ID** : `ASSUMP-006`
- **Sujet** : Statut des coûts
- **Nature** : `CHOIX DU PROJET` (méthode) + `FAIT EXTÉRIEUR` (montants)
- **Proposition** : chaque coût porte un statut `CONFIRMED`, `ASSUMED`, `UNKNOWN` ou non applicable. Le glissement de 0,5 pip est un **scénario expérimental**. Commission, frais de conversion, financement overnight et prime de stop garanti restent `UNKNOWN` jusqu'à une preuve applicable. Un coût inconnu n'est jamais compté zéro : il bloque une conclusion réaliste sur IG et le dimensionnement réel, **pas** l'écriture du moteur hors ligne, où il reste un paramètre explicite.
- **Statut** : `APPROVED` (2026-10-30, ADR-008) pour la **méthode** ; 0,5 pip reste un scénario expérimental ; les montants restent inconnus

- **ID** : `ASSUMP-007`
- **Sujet** : Taux de conversion USD → EUR
- **Nature** : `CHOIX DU PROJET` (convention d'estimation) + `FAIT EXTÉRIEUR` (conversion facturée)
- **Proposition** : 1 / bid EUR/USD au moment du calcul, comme convention **prudente d'estimation de la perte au stop**. Ce n'est ni la conversion facturée par IG ni une règle à appliquer indistinctement aux gains et aux pertes. Les frais de conversion IG sont traités séparément (ASSUMP-006).
- **Statut** : `APPROVED` (2026-10-30, ADR-008) comme **estimation de la perte au stop** seulement

- **ID** : `ASSUMP-008`
- **Sujet** : Déclenchement des stops et référence des distances minimales
- **Nature** : `FAIT EXTÉRIEUR`
- **Proposition** : deux questions distinctes.
  1. *Déclenchement* : un stop protégeant une position acheteuse est déclenché côté **bid** ; un stop protégeant une position vendeuse, côté **ask** (offer).
  2. *Référence des distances minimales* du courtier (stop normal, stop garanti) : mesurées depuis le prix de sortie courant (bid pour une position acheteuse, ask pour une position vendeuse).
- **Raisonnement** : convention usuelle des CFD, non confirmée dans la référence IG consultée. Elle détermine que le spread est compté une seule fois, via l'entrée.
- **Garde dans le code** : `BrokerConventions.stop_trigger_side`, `normal_stop_distance_reference` et `guaranteed_stop_distance_reference` sont vides ; le dimensionnement est bloqué tant qu'ils ne portent pas une `Confirmation` (source, date, epic). Une confirmation différente de la convention implémentée bloque aussi.
- **Statut** : `PROPOSED` — fait extérieur, ouvert : confirmations attendues, question posée dans `docs/IG_SUPPORT_REQUEST.md`

- **ID** : `ASSUMP-009`
- **Sujet** : Âge maximal d'une cotation pour une entrée
- **Nature** : `CHOIX DU PROJET`
- **Proposition** : 10 secondes, mesuré sur le champ `TIMESTAMP` (UTC, millisecondes) du flux `PRICE`, jamais sur l'heure de réception locale. **Paramètre expérimental de fonctionnement**, à mesurer ensuite ; ni exigence IG ni seuil universel pour les neuf stratégies.
- **Statut** : `APPROVED` (2026-10-30, ADR-008) comme paramètre expérimental de fonctionnement

- **ID** : `ASSUMP-010`
- **Sujet** : Âge maximal des fonds propres du robot
- **Nature** : `CHOIX DU PROJET`
- **Proposition** : 5 minutes, **paramètre expérimental**. Le délai ne dispense jamais d'intégrer positions, frais et mouvements de fonds : tout événement non intégré invalide les fonds propres, quelle que soit leur date. Le suivi des fonds propres reste à construire.
- **Statut** : `APPROVED` (2026-10-30, ADR-008) avec invalidation par tout événement non intégré

- **ID** : `ASSUMP-011`
- **Sujet** : Âge maximal de la vérification du contrat
- **Nature** : `CHOIX DU PROJET`
- **Proposition** : 60 secondes, mesuré sur l'heure de réception locale de `GET /markets/{epic}` v3 (aucun horodatage IG exploitable). Paramètre expérimental. Toute contradiction entre l'état du contrat (REST) et l'état de la cotation (flux `PRICE`) bloque l'entrée ; aucune source ne l'emporte : il faut une nouvelle vérification récente concordante.
- **Statut** : `APPROVED` (2026-10-30, ADR-008) comme paramètre expérimental ; blocage en cas de contradiction conservé

- **ID** : `ASSUMP-012`
- **Sujet** : Interprétation de `DLG_FLAG` (flux `PRICE`)
- **Nature** : `CHOIX DU PROJET` (politique restrictive) + `FAIT EXTÉRIEUR` (signification des valeurs)
- **Proposition** : seule la valeur `DEAL` est considérée comme négociable ; toutes les autres (`CLOSED`, `CALL`, `EDIT`, `CLOSINGSONLY`, `DEALNOEDIT`, `AUCTION`, `AUCTIONNOEDIT`, `SUSPEND`) bloquent. Les espaces finaux (présents dans la liste documentée par IG et observés sur la démo) sont ignorés. Cette politique n'établit pas la signification des autres valeurs.
- **Statut** : `APPROVED` (2026-10-30, ADR-008) comme politique restrictive ; la signification des autres valeurs reste un fait extérieur ouvert

- **ID** : `ASSUMP-013`
- **Sujet** : Champ `DELAY` absent sur la démo
- **Nature** : `OBSERVATION` + `CHOIX DU PROJET` (politique de blocage)
- **Proposition** : *observation* : `DELAY` a été demandé mais n'a jamais été reçu avec une valeur sur la démo (2026-10-27). *Politique* : une valeur absente ou inconnue bloque les **entrées** (« indicateur de cotation différée inconnu »), elle n'est pas lue comme « non différé ». Ce blocage ne concerne pas les travaux historiques hors ligne.
- **Statut** : `APPROVED` (2026-10-30, ADR-008) pour le blocage des entrées ; question toujours posée dans `docs/IG_SUPPORT_REQUEST.md`

- **ID** : `ASSUMP-014`
- **Sujet** : Verrouillage du flux sur la démo
- **Nature** : `CHOIX DU PROJET` + `OBSERVATION`
- **Proposition** : `reroutingEnvironment` est renvoyé vide par la démo ; la sonde actuelle refuse toute valeur autre que vide ou `DEMO` et exige un hôte Lightstreamer d'une liste explicite (`demo-apd.marketdatasystems.com`, observé le 2026-10-27). Un nouvel hôte arrête la sonde jusqu'à revue (la documentation IG indique que l'adresse peut changer).
- **Statut** : `APPROVED` (2026-10-30, ADR-008) pour la sonde actuelle

- **ID** : `ASSUMP-015`
- **Sujet** : Ancrage des bougies H4 et D1
- **Nature** : `CHOIX DU PROJET`
- **Proposition** : convention du robot : clôture de New York (journée 17:00 → 17:00 America/New_York ; H4 à 17, 21, 01, 05, 09, 13 h New York) ; H1 sur l'heure UTC ; le dimanche soir appartient au lundi. Même ancrage en recherche et en fonctionnement ; il n'est pas nécessaire de reproduire les bougies des graphiques IG (les bougies du direct seront reconstruites depuis le flux `PRICE`).
- **Statut** : `APPROVED` (2026-10-30, ADR-008) comme convention du robot

- **ID** : `ASSUMP-016`
- **Sujet** : Fermeture hebdomadaire et fermetures particulières
- **Nature** : `CHOIX DU PROJET` (calendrier de travail) + `FAIT EXTÉRIEUR` (fermetures particulières)
- **Proposition** :
  1. *Calendrier hebdomadaire de travail* : fermeture du vendredi 17:00 au dimanche 17:00 New York.
  2. *Fermetures particulières* (jours fériés, fermetures anticipées) : **non confirmées** tant que leur période exacte n'est pas établie par une source applicable. Le 25 décembre et le 1er janvier restent marqués « jour férié probable » : bougies incomplètes, jamais classées silencieusement en fermeture normale, et `INTERRUPTION_INEXPLIQUÉE` pour S1 (ASSUMP-023).
- **Statut** : `APPROVED` (2026-10-30, ADR-008) pour le calendrier hebdomadaire de travail ; fermetures particulières non confirmées (fait extérieur ouvert)

- **ID** : `ASSUMP-017`
- **Sujet** : Seuil de trou de cotation
- **Nature** : `CHOIX DU PROJET`
- **Proposition** : un intervalle sans tick valide de plus de 10 minutes pendant l'ouverture prévue rend les bougies concernées incomplètes (seuil de qualité des données). Un silence plus court n'est **pas** une garantie de cotation fraîche pour exécuter une entrée (ASSUMP-009).
- **Statut** : `APPROVED` (2026-10-30, ADR-008) comme seuil de qualité des données

- **ID** : `ASSUMP-018`
- **Sujet** : Conditions d'utilisation des données Dukascopy
- **Nature** : `FAIT EXTÉRIEUR` (licence, ambiguë)
- **Proposition** : l'**ambiguïté de licence n'est pas résolue** : conservation persistante hors cache (« temporary use »), conversion en Parquet et bougies (« adapt, modify »), usage pour un compte chez un autre courtier, apprentissage, conditions du compte démo (`docs/DATA.md` §1.2-1.3). La décision d'acquérir malgré cette ambiguïté est une **décision de l'opérateur**, consignée séparément (ADR-004) ; elle ne résout pas l'ambiguïté. Question préparée : `docs/DUKASCOPY_REQUEST.md`, non envoyée par décision de l'opérateur. Pas de téléchargement automatisé depuis le site (CGU du site, section 3).
- **Statut** : `PROPOSED` — fait extérieur, ambiguïté ouverte ; acquisition couverte par ADR-004

- **ID** : `ASSUMP-019`
- **Sujet** : Formats et convention temporelle des données Dukascopy
- **Nature** : `FAIT EXTÉRIEUR` + `OBSERVATION`
- **Proposition** : deux adaptateurs distincts.
  1. *Export manuel du site* (`dukascopy-ticks-csv-v1`, non utilisé pour l'historique actuel) : en-tête `Gmt time,Ask,Bid,AskVolume,BidVolume`, date `dd.MM.yyyy HH:mm:ss.SSS`, 5 décimales, temps **déclaré** GMT/UTC (non documenté).
  2. *SDK JForex* (`jforex-sdk-ticks-csv-v1`, source de l'historique 2015-2023) : `time_ms,ask,bid,ask_volume,bid_volume` ; `ITick.getTime()` sans unité ni fuseau documentés, lu en millisecondes UTC.
- **Observations** (contrôles de cohérence, pas des preuves) : sur 2015-2023, 466 dernières cotations sur 470 et 459 réouvertures sur 469 à moins de 5 min de l'horaire attendu ; lors des 18 changements d'heure américains, la réouverture se décale d'une heure le bon week-end (écart de 0,0 à 0,4 min) (`docs/DATA.md` §6).
- **Statut** : `PROPOSED` — fait extérieur, ouvert : convention temporelle toujours non documentée

- **ID** : `ASSUMP-020`
- **Sujet** : Paramètres de la fiche S1
- **Nature** : `CHOIX DU PROJET`
- **Proposition** : configuration initiale **expérimentale** à tester, pas des paramètres démontrés rentables : N = 20, M = 10, ATR 14, k = 2, signal sur la série bid, filtre D1 au milieu du canal de 55 jours **incluant la D1 de contexte** (les 55 D1 qui se terminent par elle ; c'est aussi la fenêtre de la mesure de disponibilité de la fiche S1 §10.4). Aucun réglage ni résultat.
- **Statut** : `APPROVED` (2026-10-30, ADR-008) comme configuration initiale expérimentale, canal D1 incluant la D1 de contexte ; pas des paramètres démontrés rentables

- **ID** : `ASSUMP-021`
- **Sujet** : Découpage des requêtes JForex
- **Nature** : `CHOIX DU PROJET` (fondé sur un `FAIT EXTÉRIEUR` documenté)
- **Proposition** : fenêtres d'une heure ; demander `[début − 1 ms, fin − 1 ms]` puis garder `début ≤ t < fin`, filtrage sur le temps uniquement. Aucun tick dupliqué ni supprimé aux frontières ; ticks simultanés conservés (`src/forex_bot/history/jforex.py`, tests de frontières). Sources : le wiki officiel (« History ticks ») indique que `from` et `to` sont **tous deux inclusifs** ; la Javadoc ne le précise que pour `to`. La règle reste correcte dans les deux cas.
- **Statut** : `APPROVED` (2026-10-30, ADR-008)

- **ID** : `ASSUMP-022`
- **Sujet** : Heures vides renvoyées par le SDK JForex
- **Nature** : `CHOIX DU PROJET` (fondé sur une `OBSERVATION`)
- **Proposition** : une heure sans tick alors que le marché est attendu ouvert est une **acquisition incomplète**, pas la preuve d'une absence de cotation : suppression du fichier de cache de 0 octet de cette heure, jusqu'à 5 tentatives, puis jour non écrit (`<jour>.incomplete.json`). Fondé sur l'observation du 2026-10-28 (réponse HTTP 503 transformée en liste vide et mise en cache) ; structure du cache observée, non documentée. Les heures des jours fériés probables (ASSUMP-016) ne sont pas relancées. **Seule exception** : la liste fermée `ACCEPTED_EMPTY_HOURS` (2016-09-02 18h, 2019-05-26 21h et 22h UTC), décidée par l'opérateur (ADR-005) ; ces heures restent signalées et ne sont jamais comblées.
- **Statut** : `APPROVED` (2026-10-30, ADR-008)

- **ID** : `ASSUMP-023`
- **Sujet** : Règles de données de S1 (états des bougies, ATR, canal D1, sorties, positions pendant une interruption, chronologie)
- **Nature** : `CHOIX DU PROJET`
- **Proposition** : `docs/strategies/S1_DONCHIAN.md` §5 et §10. À chaque décision, seule l'information disponible à cet instant est utilisée : l'état connaissable à la clôture (`complete_at_close`) est le point de départ ; une information apparue depuis sert aux décisions suivantes sans réécrire les décisions passées ; l'audit rétrospectif (`complete`) n'est jamais utilisé. États `OK` / `FERMETURE_DOCUMENTÉE` / `COUVERTURE_PARTIELLE` / `INTERRUPTION_INEXPLIQUÉE`. Canal D1 **strict** ; variante sans filtre D1 distincte. ATR indisponible puis réamorcé sur 14 true ranges valides. Sortie stratégique calculable distincte d'une liquidation de sécurité. Positions pendant une interruption : scénarios explicites, hypothèses sans garantie d'encadrer le résultat réel. Coûts inconnus paramétrés, jamais nuls.
- **Statut** : `APPROVED` (2026-10-30) comme **règles de référence expérimentales** de S1 ; ni validation de performance ni autorisation de trading (ADR-006). Harmonisation de la fiche du 2026-10-30 à relire avec ce lot.

- **ID** : `ASSUMP-024`
- **Sujet** : Conventions comptables et d'exécution du moteur S1 (revue d'Astra du 2026-10-31)
- **Nature** : `CHOIX DU PROJET`
- **Proposition** : `docs/strategies/S1_DONCHIAN.md` §5, §6 et §8.
  1. *Priorité sur un tick* : silence précédent, puis stop de la position ouverte, puis sortie au canal en attente, puis entrée en attente. Un stop franchi sur le tick qui exécuterait la sortie au canal l'emporte (ordre de stop déjà en place) ; la sortie au canal est abandonnée et journalisée.
  2. *Fonds propres* : solde réalisé (modifié seulement à la clôture), résultat latent (valeur de liquidation de la position au dernier tick connu : prix côté sortie, coûts de sortie accumulés, conversion du côté défavorable, sans prime de stop garanti), fonds propres = solde + latent. Courbe échantillonnée à chaque décision H4 et à chaque sortie ; une position encore ouverte à la fin de l'étude est valorisée, jamais clôturée artificiellement. Le drawdown mesuré sur cet échantillon ne voit pas les extrêmes entre deux échantillons.
  3. *Taille* : fixée à `D`, avant l'envoi simulé, sur les fonds propres estimés avec le dernier tick strictement antérieur à `D`. Lors d'un retournement, ils incluent le latent de la position en cours de sortie.
  4. *Entrée exécutée* : jamais supprimée après coup au vu de son prix d'exécution. Son risque au prix exécuté est enregistré avec le dépassement éventuel du budget (`DÉPASSEMENT_RISQUE`). Un refus fondé sur l'écart d'exécution n'est admissible que s'il est modélisé comme un ordre conditionnel explicite (non implémenté).
- **Raisonnement** : recommandations de la revue d'Astra ; refuser rétrospectivement une transaction à partir de son futur prix d'exécution favoriserait artificiellement le backtest.
- **Statut** : `PROPOSED` — à valider par l'opérateur
