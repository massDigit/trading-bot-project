# DATA.md - Données historiques

> Lot « historiques EUR/USD », branche `feat/eurusd-history-s1`. Recherche uniquement : aucun
> lien avec l'exécution d'ordres.
> Les cotations Dukascopy **ne sont pas** les prix exécutables chez IG (spread, horaires,
> ajustements et exécution diffèrent). Elles servent à la recherche, pas à reproduire IG.

## 1. Source : Dukascopy (étude du 2026-10-27, acquisition à partir du 2026-10-28)

Trois niveaux sont distingués : **capacité technique documentée** (DOC), **conditions
d'utilisation** (CGU / licence), **observation réellement vérifiée** (OBS). Les données sont
acquises par le canal B uniquement (§1.4), depuis le 2026-10-28.

### 1.1 Canaux d'accès

| Canal | Capacité technique documentée | Conditions applicables | Vérifié |
|---|---|---|---|
| A. Export web manuel (« Historical Data Export ») | CSV, « from tick-by-tick to monthly » ; colonnes, format de date et fuseau **non documentés** | CGU du site (§1.2) | rien |
| B. JForex SDK, interface `IHistory` | Java ; `getTicks(instrument, from, to)` charge les ticks « from the server into local cache » ; `ITick` : `getBid`, `getAsk`, `getBidVolume`, `getAskVolume` ; barres par `OfferSide.BID` / `ASK` ; dépôt Maven officiel (`JForex-API` 2.13.99, `DDS2-jClient-JForex` 3.6.51, mis à jour le 2025-10-17) | Licence de l'API JForex (§1.3) ; CGU du site pour l'accès au site ; conditions du compte démo non consultées | **OBS** : utilisé, voir §1.4 |
| C. Fichiers horaires `datafeed` (format binaire) | Aucune documentation officielle | Non étudié ; non utilisé | rien |

Les restrictions de scraping des CGU du **site** ne sont pas transposées automatiquement au SDK
officiel ; inversement, la disponibilité du SDK n'établit aucun droit de conservation ou de
réutilisation.

OBS (journaux du SDK, 2026-10-28) : pour l'historique de ticks, le SDK télécharge lui-même des
fichiers horaires `.bi5` depuis un hôte `datafeed` de Dukascopy et les place dans son cache. Le
projet n'accède jamais directement à cet hôte : il passe uniquement par l'interface `IHistory`.

### 1.2 CGU du site (Terms of Use, consultées le 2026-10-27, sans date d'effet)

- Section 3 : usage « solely for your own non-commercial use » ; interdiction de « any "scraper,"
  "robot," "bot," "spider," "data mining" […] without the prior express written consent » ;
  « The WEBSITE and the information contained therein may not be used to construct a database of
  any kind ».
- Section 4 : téléchargement « licensed to you by DUKASCOPY ONLY for your own personal,
  non-commercial use ».
- Section 7 : données « AS IS », sans garantie d'exactitude ni de complétude.

Pour le canal A, un export manuel est permis pour un usage personnel non commercial, mais **la
conservation dans une base locale** reste ambiguë (« may not be used to construct a database of
any kind ») : l'export manuel ne lève pas cette ambiguïté.

### 1.3 Licence de l'API JForex (« Terms of Use », page Javadoc, sans date ni version)

- Section 1 : licence « non-exclusive, non-transferable, worldwide license for personal,
  non-commercial […] temporary use of and access to the Dukascopy™ JForex API, all the images,
  materials, any other data or information it contains » ; « Licensor reserves the right to
  define the limits of non-commercial use of Content » ; l'EULA citée n'est pas reproduite.
- Section 2 : interdiction de « translate into another programming language, port, adapt,
  modify, […] store for commercial use any part of Content or any derivatives thereof ».
- Section 8 : mention « Powered by Dukascopy™ » lorsque le contenu est intégré à une API.
- Section 12 : les clients d'un courtier enregistré sont liés par les CGU Dukascopy.

**Ce qui couvre explicitement notre usage** : l'accès aux données historiques via l'API pour un
usage personnel et non commercial.
**Ce qui reste ambigu** :
1. la conservation **persistante** hors du cache JForex, alors que la licence parle d'usage
   « temporary » et que seule la conservation « for commercial use » est expressément interdite ;
2. la conversion en Parquet et l'agrégation en bougies, au regard de « adapt, modify » et de la
   limite de modification « to fit the format, look and feel of the Licensee's JForex API » ;
3. la qualification d'une recherche personnelle servant à décider de positions sur un compte
   tenu chez un **autre** courtier (IG), puisque Dukascopy « reserves the right to define the limits
   of non-commercial use » ;
4. l'usage pour l'apprentissage d'un modèle (cahier des charges §5) ;
5. les conditions du compte démo nécessaire à la connexion, et le texte de l'EULA.

Une question ciblée est préparée, **non envoyée** : `docs/DUKASCOPY_REQUEST.md`.

**Décision de l'opérateur (2026-10-28)** : malgré ces ambiguïtés, l'acquisition est faite par le
canal B pour un usage strictement personnel et non commercial ; la question n'est pas envoyée. Si
Dukascopy émet un avertissement, l'acquisition et l'usage s'arrêtent et les données sont purgées.
Les données restent locales (`data/`, hors Git), ne sont jamais redistribuées ni publiées, et
restent séparables des autres sources.

### 1.4 Acquisition par le SDK JForex (canal B) : adaptateur `tools/jforex-ticks`

| Point | État |
|---|---|
| Compte | Compte **démo** JForex ouvert par l'opérateur (expire après 14 jours). Identifiants lus dans le fichier d'environnement passé en argument (`DUKASCOPY_USERNAME`, `DUKASCOPY_PASSWORD`), seules ces deux clés sont lues ; masqués dans toutes les sorties |
| Serveur | Adresse démo figée dans le code (`https://platform.dukascopy.com/demo/jforex.jnlp`) ; aucun code PIN (exigé par les serveurs réels) |
| Lecture seule | Une stratégie vide sert uniquement à obtenir `IHistory` ; le moteur d'ordres (`getEngine`) n'est jamais appelé. Test statique : `test_java_adapter_is_read_only_and_demo_only` |
| Période | Refus de toute période hors `[2015-01-01, 2024-01-01)` : le test final 2024-2025 est inaccessible |
| Environnement | Java 21 (OpenJDK Homebrew, arm64) et Maven ; SDK `DDS2-jClient-JForex` 3.6.51 depuis le dépôt Maven officiel en HTTPS. **OBS** : fonctionne sur Mac M4 |
| Bornes | Une fenêtre par heure UTC : demande `[début − 1 ms, fin − 1 ms]`, conservation de `début ≤ t < fin` (`src/forex_bot/history/jforex.py`). OBS sur l'échantillon : 0 tick hors fenêtre, 0 désordre |
| Horodatage | OBS : `getTime()` se lit en millisecondes ; interprété en UTC. Contrôle de cohérence : dernier tick du vendredi et premier du dimanche à moins de 0,1 min de l'horaire attendu, avant et après le changement d'heure américain (ce n'est pas une preuve) |
| Sortie | Un CSV par jour UTC `data/dukascopy-sdk/ticks/EURUSD/<jour>.csv` (`time_ms,ask,bid,ask_volume,bid_volume`, valeurs du SDK sans conversion) et un JSON compagnon (période, date de récupération, ticks par heure, nouvelles tentatives, durée). Écriture atomique ; le CSV est écrit en dernier et marque le jour comme terminé |
| Reprise | Un jour dont le CSV existe est sauté : un lancement interrompu reprend au premier jour manquant |
| Cache du SDK | `data/dukascopy-sdk/cache` (purgeable). Le SDK crée aussi `~/Library/Application Support/JForex/` hors du projet |
| **Défaut observé : réponses 503** | OBS (2026-10-28) : quand l'hôte `datafeed` répond HTTP 503, `getTicks` renvoie une liste **vide sans erreur** et le cache garde un fichier de 0 octet pour l'heure : toutes les demandes suivantes de cette heure reviennent vides. Au premier passage, 7 heures de semaine ont été perdues ainsi. Traitement : avant chaque demande d'une heure où le marché est attendu ouvert, un fichier de cache de 0 octet de cette heure est supprimé (structure du cache observée, non documentée : `EURUSD/<année>/<mois 0-11>/<jour>/<HH>h_ticks.bi5`) ; une heure ouverte vide est relancée jusqu'à 5 fois (pauses de 5 à 40 s) ; si elle reste vide, le jour **n'est pas écrit** et un rapport `<jour>.incomplete.json` l'explique |
| **Heures vides acceptées (décision opérateur 2026-10-30)** | Deux jours sont restés incomplets après 4 tentatives sur 3 sessions étalées sur environ 36 h, toujours sur les mêmes heures, avec des réponses 503 répétées alors que les heures voisines se chargeaient : **2016-09-02 18h UTC** (vendredi, publication de l'emploi américain ; 17h ne compte que 1 815 ticks) et **2019-05-26 21h et 22h UTC** (réouverture du dimanche ; 23h ne compte qu'un tick). Interprétation : fichiers probablement absents ou abîmés à la source, non prouvé. Traitement : liste fermée `ACCEPTED_EMPTY_HOURS` dans l'adaptateur ; ces heures restent demandées et relancées, et si elles restent vides le jour est écrit **sans les combler**, le JSON compagnon les liste (`accepted_empty_hours_utc`), le rapport qualité les montre comme trous et marque les bougies. Toute autre heure ouverte vide bloque toujours son jour. Test : `test_java_adapter_accepts_only_the_operator_listed_empty_hours` |
| Jours fériés | Même calendrier que `calendar.py` : les heures des jours fériés probables (25 décembre, 1er janvier) ne sont pas relancées et sont acceptées vides ; le rapport qualité les marque. OBS (2026-10-28) : sur le 1er janvier 2015, le serveur répondait 503, des délais dépassés et des connexions réinitialisées ; l'adaptateur l'a relancé pendant 35 min sans terminer, alors qu'un jour ouvré de 2015 se télécharge en 52 s sans erreur |
| Rythme | Pause de 250 ms après chaque requête horaire ; OBS : environ 6,5 s par jour sans 503 |
| Import | `forex-history ingest-jforex --dir data/dukascopy-sdk/ticks/EURUSD` : chaque jour complet passe par l'importeur (brut immuable, manifeste, Parquet), format `jforex-sdk-ticks-csv-v1` |

## 2. Échantillon

Défini **avant** tout examen de données dans `config/history/sample_eurusd_2019_03.toml` :
EUR/USD, 2019-03-07 00:00 → 2019-03-13 00:00 UTC (6 jours), partition de **développement**.
Il couvre plusieurs sessions, la clôture du vendredi 8 mars, la réouverture du dimanche 10 mars et
le passage à l'heure d'été américaine du 10 mars 2019 ; aucune donnée 2022-2025.

Statut : **acquis le 2026-10-28** par le SDK (§1.4). Résultat : 530 478 ticks sur 6 jours,
0 prix invalide, 0 cotation croisée, 0 désordre, 0 heure d'ouverture sans tick ; spread médian
0,3 pip (95e centile 0,4 pip, maximum 5,4 pips) ; 97 bougies H1 complètes. Le premier passage
avait perdu 7 heures (défaut 503, §1.4), corrigées au second.

Acquisition complète décidée par l'opérateur le 2026-10-28 : 2015-01-01 → 2024-01-01
(développement et validation).

### Convention temporelle

La convention d'horodatage doit venir de la documentation de l'interface utilisée. Pour l'export
CSV, elle n'est que **déclarée** (colonne « Gmt time ») ; pour JForex, l'unité et le fuseau de
`getTime()` ne sont pas documentés. La fermeture du vendredi et la réouverture du dimanche sont
des **contrôles de cohérence**, pas une preuve du fuseau.
Pour le SDK : `getTime()` est lu en millisecondes UTC (§1.4) ; même statut de cohérence.

## 3. Découpage d'évaluation (cahier des charges §9)

| Partition | Période | Usage |
|---|---|---|
| Développement | 2015-2021 | Exploration, réglages, entraînement |
| Validation | 2022-2023 | Validation des candidates et du sélecteur ; pas de réglage |
| Test final | 2024-2025 | **Réservé** : l'importeur refuse toute période qui le touche |

## 4. Importeur (`src/forex_bot/history/`)

| Exigence | Mise en œuvre |
|---|---|
| Brut immuable | Copie dans `data/raw/<source>/<instrument>/<sha256>.csv`, lecture seule ; jamais réécrite |
| Traçabilité | Manifeste JSON : source, instrument, format, période déclarée, date de récupération, nom d'origine, taille, empreinte, partitions |
| Empreinte | SHA-256 du fichier ; vérifiée après copie |
| Reprise | Écritures dans un fichier temporaire puis renommage atomique ; les temporaires orphelins sont supprimés au lancement suivant ; chaque étape déjà faite est sautée |
| Idempotence | Même empreinte = aucune action ; un fichier différent dont la période chevauche un fichier importé est **refusé** |
| Erreurs | Format non conforme : arrêt avec numéro de ligne, rien n'est publié |
| Limites de requêtes | Sans objet pour l'importeur (aucune requête réseau) ; voir §1.4 pour l'adaptateur |
| Stockage | Parquet ; prix en `decimal128(18,5)` ; horodatage `timestamp[us, UTC]` |

### Doublons et ticks simultanés

Deux ticks au même horodatage ne sont **pas** des doublons : la source peut publier plusieurs
cotations dans la même milliseconde. Tous sont conservés, ordonnés par leur ligne dans le fichier.
Les doublons sont évités **au niveau des fichiers** (empreinte identique ou périodes
chevauchantes). Les lignes consécutives strictement identiques (heure, prix, volumes) sont
comptées mais conservées, car indiscernables d'une cotation répétée.

### Schéma des ticks normalisés

| Colonne | Type | Remarque |
|---|---|---|
| `source`, `instrument` | string | |
| `ts_utc` | timestamp[us, UTC] | horodatage du fournisseur ; convention déclarée par le format, cohérence contrôlée |
| `raw_sha256`, `raw_row` | string, int64 | provenance et ordre des ticks simultanés |
| `bid`, `ask` | decimal128(18,5) | séparés ; aucun spread calculé ni inventé |
| `bid_volume`, `ask_volume` | float64 | volume du fournisseur, unité non confirmée |

## 5. Bougies H1, H4, D1 (configuration de travail, non approuvée définitivement)

- Bid et ask agrégés **séparément** à partir des mêmes ticks valides ; `tick_count` = nombre de
  ticks valides (type de volume).
- **H1** : début à chaque heure UTC (identique en heure de New York, décalage entier).
- **H4 et D1** : ancrage sur la clôture de New York (ASSUMP-015). Journée de 17:00 à 17:00
  America/New_York ; H4 à 17:00, 21:00, 01:00, 05:00, 09:00, 13:00 New York. En UTC : D1 à
  22:00 (hiver américain) ou 21:00 (été américain).
- **Dimanche** : la séance qui rouvre le dimanche à 17:00 New York appartient au lundi ; il n'y a
  pas de bougie D1 du dimanche.
- **Changements d'heure** : aux États-Unis, ils ont lieu le dimanche à 02:00, pendant la
  fermeture : aucune bougie H4 ou D1 ne les chevauche. Les frontières UTC se décalent d'une heure.
  Les changements européens n'affectent pas cet ancrage (ils compteront pour les stratégies de
  session, D1-DAY par exemple).
- **Fermeture hebdomadaire prévue** : vendredi 17:00 → dimanche 17:00 New York (ASSUMP-016). Le
  25 décembre et le 1er janvier sont marqués « jour férié probable ».
- **Bougie complète** si : dans la couverture déclarée, toutes les heures d'ouverture prévues
  présentes et complètes, aucun trou de cotation > 10 min pendant l'ouverture prévue
  (ASSUMP-017), aucun tick pendant la fermeture prévue, pas de jour férié probable.
- **Bougie incomplète** : conservée et marquée (`complete = false`, `flags`) ; jamais comblée. Une
  bougie qui dépasse la fin de la couverture est « non clôturée » et inutilisable.
- H4 et D1 sont agrégées à partir des H1 (frontières sur des heures pleines : résultat identique
  à une agrégation des ticks).

## 6. Rapport qualité

`data/reports/quality_<source>_<instrument>.{json,md}` : couverture, ordre chronologique,
ticks simultanés et répétitions, prix invalides et cotations croisées, interruptions classées
(fermeture normale, jour férié probable, **trou**), heures d'ouverture sans tick, **contrôle de
cohérence** de la convention temporelle (dernier tick avant la clôture du vendredi et premier tick
après la réouverture du dimanche, comparés à l'horaire prévu ; ce n'est pas une preuve du fuseau), bougies complètes et incomplètes, et tableau du traitement
de chaque anomalie (conservée, exclue ou marquée, avec justification).

## 7. Commandes

```bash
uv run forex-history plan --sample config/history/sample_eurusd_2019_03.toml
uv run forex-history ingest --file <export.csv> \
    --period-start 2019-03-07T00:00:00+00:00 --period-end 2019-03-08T00:00:00+00:00 \
    --retrieved-at <date de l'export, UTC>
# Canal B (SDK JForex, démo) : téléchargement puis import
tools/jforex-ticks/run.sh --env-file <fichier d'environnement> --from 2015-01-01 --to 2024-01-01
uv run forex-history ingest-jforex --dir data/dukascopy-sdk/ticks/EURUSD
uv run forex-history build      # bougies H1/H4/D1 + rapport qualité
uv run forex-history status
uv run forex-history purge-dukascopy             # liste ; --confirm pour supprimer (avertissement Dukascopy)
```

Le répertoire `data/` (bruts, Parquet, rapports) est exclu de Git ; seuls le code, les schémas
et les configurations sont versionnés.
