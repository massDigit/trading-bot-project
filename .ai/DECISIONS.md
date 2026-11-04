# DECISIONS.md - Architecture Decision Records (ADR)

> **Registre chronologique des choix techniques et d'architecture.**
>
> Statuts : `ACCEPTED` | `SUPERSEDED` | `DEPRECATED`. Une proposition `APPROVED` dans `.ai/ASSUMPTIONS.md` devient un ADR `ACCEPTED` ici.

---

### ADR-001 : Initialisation du socle IA-Native
- **Date** : 2026-08-08
- **Statut** : `ACCEPTED`
- **Contexte** : Nécessité de structurer le projet pour une collaboration homme-IA optimale et interopérable.
- **Décision** : Adoption de l'architecture standardisée avec routage master `AGENTS.md`, `.ai/` et `.agents/skills/`.
- **Conséquences** : Tout agent IA doit respecter le parcours de lecture obligatoire.

### ADR-002 : Conteneurisation Docker différée jusqu'au besoin d'exécution continue
- **Date** : 2026-10-29
- **Statut** : `ACCEPTED` (décision de l'opérateur)
- **Contexte** : Le projet tourne aujourd'hui sur le poste de l'opérateur (macOS), en tâches ponctuelles : diagnostic IG, récupération d'historique, construction des bougies. La reproductibilité est assurée par `uv.lock` (Python et dépendances) et par `tools/jforex-ticks/pom.xml` et `run.sh` (SDK JForex, Java 21). Sur macOS, Docker s'exécute dans une machine virtuelle qui se fige pendant la veille, comme le reste du poste : il n'aurait pas évité l'arrêt de la récupération du 2026-10-29 dû à la veille sur batterie faible. Il réserverait aussi une part de la mémoire et ralentirait l'accès aux données volumineuses dans `data/`.
- **Décision** : Pas de conteneurisation tant que le besoin n'existe pas. Docker sera mis en place lorsque le robot devra tourner en continu sur une machine dédiée (serveur, VPS), par exemple pour un essai prolongé en démo puis en réel.
- **Conséquences** : Aucun `Dockerfile` ni `docker-compose` pour l'instant. Le lot « exécution continue » devra inclure : une image reproductible, des identifiants injectés à l'exécution (jamais dans l'image), une politique de redémarrage, et une reconnexion gérée dans le code, que Docker ne fournit pas.

### ADR-003 : Contrat cible EUR/USD Mini, allocation et règle du stop
- **Date** : 2026-10-27
- **Statut** : `ACCEPTED` (décision de l'opérateur)
- **Source** : demande de l'opérateur du 2026-10-27 après validation du diagnostic démo (lot de la PR #2).
- **Décision** : le robot vise le contrat EUR/USD **Mini** d'IG (`CS.D.EURUSD.CEFM.IP`), sélectionné explicitement ; allocation initiale de **2 000 EUR** ; dimensionnement sur la perte estimée au stop, conversion USD → EUR et coûts compris ; « ne jamais réduire la distance technique du stop pour faire entrer une position dans le budget : réduire la taille ou refuser le signal ».
- **Portée** : choix du projet. Les unités, minimums, incréments, conventions de stop et coûts IG restent des faits extérieurs à confirmer (ASSUMP-004 à 008) ; tant qu'ils ne le sont pas, le dimensionnement exécutable reste bloqué.
- **Conséquences** : ASSUMP-003 (pas d'epic figé) est dépassée ; la recherche dynamique reste un outil de diagnostic.

### ADR-004 : Historique de recherche Dukascopy par le SDK JForex, EUR/USD 2015-2023
- **Date** : 2026-10-28
- **Statut** : `ACCEPTED` (décision de l'opérateur)
- **Source** : messages de l'opérateur du 2026-10-28 (« On peut quand même essayer, et si jamais on reçoit un avertissement […] on arrêtera » ; pas de question envoyée à Dukascopy ; une seule paire ; « Point de départ : 2015. La récupération complète »).
- **Décision** : acquérir l'historique de ticks EUR/USD par le SDK JForex (serveur démo, lecture seule, interface `IHistory` uniquement), du 2015-01-01 au 2024-01-01 (développement et validation), **malgré l'ambiguïté de licence**, pour un usage strictement personnel et non commercial. Données locales hors Git, jamais redistribuées. En cas d'avertissement de Dukascopy : arrêt et purge (`forex-history purge-dukascopy --confirm`).
- **Portée** : n'interprète pas la licence et ne résout pas son ambiguïté (ASSUMP-018). Dukascopy sert de proxy de recherche : ses cotations ne sont pas les prix exécutables chez IG. La période de test final 2024-2025 n'est pas acquise.
- **Conséquences** : acquisition terminée le 2026-10-30 avec exceptions connues (ADR-005).

### ADR-005 : Heures absentes à la source acceptées sans comblement
- **Date** : 2026-10-30
- **Statut** : `ACCEPTED` (décision de l'opérateur)
- **Source** : choix de l'opérateur du 2026-10-30 (« Vas-y pour l'option dans l'adaptateur »), après quatre tentatives en échec sur environ 36 h.
- **Décision** : liste fermée `ACCEPTED_EMPTY_HOURS` dans l'adaptateur Java (2016-09-02 18h, 2019-05-26 21h et 22h UTC) : ces heures restent demandées et relancées ; si elles restent vides, le jour est écrit **sans les combler**, elles sont consignées dans le JSON du jour, apparaissent comme trous et rendent les bougies incomplètes. Toute autre heure ouverte vide bloque toujours son jour.
- **Portée** : ces deux journées restent incomplètes ; aucune absence de cotation n'est affirmée.

### ADR-006 : Règles de données de S1 comme référence expérimentale
- **Date** : 2026-10-30
- **Statut** : `ACCEPTED` (décision de l'opérateur)
- **Source** : messages de l'opérateur du 2026-10-30 : règle stricte du canal D1 retenue comme référence, puis validation d'ASSUMP-023 « comme règles de référence expérimentales de S1 ».
- **Décision** : `docs/strategies/S1_DONCHIAN.md` §5 et §10 : canal D1 strict, variante sans filtre D1 distincte, états de qualité des bougies, réamorçage de l'ATR, scénarios explicites pour les positions pendant les interruptions. Précisions de l'opérateur : à chaque décision, uniquement les informations disponibles à cet instant ; l'état à la clôture est le point de départ, les informations apparues ensuite servent aux décisions suivantes sans réécrire les décisions passées ; les scénarios pendant les trous restent des hypothèses, sans garantie d'encadrer le résultat réel ; les coûts inconnus restent explicitement paramétrés pour la recherche, jamais implicitement nuls.
- **Portée** : **ni validation de performance ni autorisation de trading**. Aucune sélection de variante sur 2022-2023 à ce stade ; aucune optimisation.
- **Conséquences** : le moteur S1 peut être écrit hors ligne, sur une branche distincte dépendant de la PR #3.

### ADR-007 : Découpage d'évaluation
- **Date** : 2026-10-27
- **Statut** : `ACCEPTED`
- **Source** : cahier des charges v1.1, §9 « Découpage proposé » (document de l'opérateur, hors dépôt) ; consigne de l'opérateur du 2026-10-27 : « aucune donnée de la période réservée au test final ».
- **Décision** : développement 2015-2021, validation 2022-2023 (sans réglage), test final 2024-2025 réservé, ouvert seulement après le gel du système. L'importeur refuse 2024-2025.
- **Portée** : règles et paramètres figés et versionnés avant la première évaluation sur 2022-2023 ; variantes enregistrées à l'avance.

### ADR-008 : Approbation des choix du projet ASSUMP-001 à 022
- **Date** : 2026-10-30
- **Statut** : `ACCEPTED` (décision de l'opérateur)
- **Source** : réponse de l'opérateur du 2026-10-30 (« j'approuve la colonne Proposition ») au tableau de classement des suppositions, établi d'après la revue externe.
- **Décision** : les **choix du projet** suivants sont approuvés, chacun dans sa portée :
  - ASSUMP-001 : Python 3.12 et uv pour le projet actuel ;
  - ASSUMP-002 : httpx et session IG v2, pour le **diagnostic** seulement ;
  - ASSUMP-003 : `SUPERSEDED` par ADR-003 (recherche dynamique conservée comme outil de diagnostic) ;
  - ASSUMP-004 : précaution sur `minStepDistance` (la valeur de l'incrément reste inconnue) ;
  - ASSUMP-006 : méthode des statuts de coûts (0,5 pip reste un scénario ; montants inconnus) ;
  - ASSUMP-007 : 1 / bid comme estimation de la perte au stop seulement ;
  - ASSUMP-009, 010, 011 : 10 s, 5 min (avec invalidation événementielle), 60 s, paramètres expérimentaux ;
  - ASSUMP-012 : `DEAL` seul, politique restrictive ;
  - ASSUMP-013 : blocage des entrées si `DELAY` est absent ;
  - ASSUMP-014 : liste explicite d'hôtes pour la sonde actuelle ;
  - ASSUMP-015 : ancrage New York, convention du robot ;
  - ASSUMP-016 : calendrier hebdomadaire de travail (fermetures particulières non confirmées) ;
  - ASSUMP-017 : seuil de qualité de 10 min ;
  - ASSUMP-020 : paramètres S1 comme configuration initiale **expérimentale** (N = 20, M = 10, ATR 14, k = 2, série bid, canal D1 de 55 jours incluant la D1 de contexte) ;
  - ASSUMP-021 : découpage des requêtes JForex ;
  - ASSUMP-022 : heure vide = acquisition incomplète, sauf exceptions d'ADR-005.
- **Portée** : choix du projet uniquement. Les **faits extérieurs** restent ouverts et ne sont pas confirmés par cette approbation : ASSUMP-005 (unités IG), ASSUMP-008 (stops et distances), ASSUMP-018 (licence Dukascopy), ASSUMP-019 (formats et heure Dukascopy), ainsi que les parts « fait extérieur » des entrées mixtes (valeur de l'incrément, montants des coûts, conversion facturée, signification de `DLG_FLAG`, fermetures particulières). Aucun paramètre n'est démontré rentable ; aucune autorisation de trading.

### ADR-009 : Conventions du moteur S1 et premier passage exploratoire
- **Date** : 2026-11-03
- **Statut** : `ACCEPTED` (décision de l'opérateur)
- **Source** : réponse de l'opérateur du 2026-11-03, après la seconde revue externe du moteur (commit `cf4d0b4`).
- **Décision** :
  1. ASSUMP-024 est validée **pour le backtest hors ligne**. Stop déjà dépassé au premier tick d'exécution : « exécutée puis liquidée » par défaut, parce que la transaction et son coût restent visibles. La liquidation sur le même tick est une **hypothèse de simulation**, ni une garantie de prudence ni une confirmation du comportement d'IG sur le compte à stop garanti obligatoire. La variante « rejetée » est conservée ; les cas sont comptés et, s'il y en a, les résultats des deux scénarios sont présentés. La perte estimée au stop est distinguée de la perte simulée effectivement comptabilisée.
  2. Le lecteur de ticks en flux et un petit passage exploratoire sont autorisés. Préalable : sur le même échantillon, lecteurs en mémoire et en flux produisent les mêmes transactions, coûts, journaux et fonds propres, y compris avec des ticks de même horodatage et à la frontière de deux fichiers. Si la comparaison passe, le passage est enchaîné sans nouvelle confirmation.
  3. Dates fixées **avant** de consulter les résultats : une courte fenêtre dans 2015-2021, précédée d'une période réservée à l'initialisation des indicateurs ; lectures bornées à ces dates ; données locales ; paramètres S1 fixes ; 2022-2025 jamais consultés. Un échantillon sans transaction reste un résultat : la fenêtre n'est pas changée pour en obtenir une.
- **Fenêtre retenue par l'agent avant tout passage** (2026-11-03) : initialisation `[2019-01-01T00:00Z, 2019-04-01T00:00Z)` (bougies seulement, aucune décision) ; étude `[2019-04-01T00:00Z, 2019-07-01T00:00Z)` (décisions et ticks). Choix : environ 64 D1 avant l'étude (canal de 55 jours avec la D1 de contexte), trois mois au milieu de la partition de développement, sans regarder les prix.
- **Portée** : recherche hors ligne. Ni validation de performance, ni autorisation de trading, ni passage d'ordre ; PR #4 en brouillon, sans fusion.

### ADR-010 : Référence S1 seule sur la période de développement 2015-2021
- **Date** : 2026-11-03
- **Statut** : `ACCEPTED` (décision de l'opérateur)
- **Source** : message de l'opérateur du 2026-11-03, après la revue de la PR #4 (commit `4c6f01a`) par Astra ; PR #4 fusionnée (`d52f24f`) sur son autorisation, le lot étant validé comme moteur de recherche hors ligne.
- **Décision** : mesurer S1 Donchian seule sur une trajectoire continue du 2015-01-01 inclus au 2022-01-01 exclu, avec le moteur vérifié, les données locales et le lecteur en flux, la configuration du passage d'avril-juin 2019 (canaux 20/10, ATR 14, stop à 2 ATR, filtre D1 strict de 55 jours, stop garanti simulé, 2 000 EUR, 0,25 %, mêmes coûts). H0 d'abord ; H1 seulement si un franchissement non observable apparaît ; comparaison « exécutée puis liquidée » / « rejetée » seulement si un stop est déjà dépassé au premier tick d'entrée ; aucun scénario retenu pour sa rentabilité. Protocole figé avant lancement : `docs/experiments/S1_REFERENCE_2015_2021.md`.
- **Portée** : référence pour comparer plus tard un modèle de sélection des signaux. Aucune optimisation, aucun entraînement, aucune donnée 2022-2025, aucun ordre ni téléchargement ; ni validation de performance ni autorisation de trading.

### ADR-011 : Expérience de granularité de taille (0,01 contrat) sur 2015-2021
- **Date** : 2026-11-03
- **Statut** : `ACCEPTED` (décision de l'opérateur)
- **Source** : message de l'opérateur du 2026-11-03, après la référence S1 seule (PR #5).
- **Décision** : S1 Donchian, avec les paramètres et coûts du passage initial, est retenue comme référence de développement 2015-2021. Une variante unique rejoue toute la trajectoire avec une taille minimale et un incrément de 0,01 contrat au lieu de 0,1, tout le reste identique, dans des fichiers distincts ; protocole figé avant lancement : `docs/experiments/S1_GRANULARITY_001.md`. Aucune autre taille ni budget testé après les résultats.
- **Portée** : hypothèse de recherche ; 0,01 contrat n'est pas confirmé chez IG. Aucune donnée 2022-2025, aucun ordre, aucun entraînement ; ni validation de performance ni autorisation de trading.

### ADR-012 : Publication des résultats des passages 2015-2021 dans la PR #5
- **Date** : 2026-11-03
- **Statut** : `SUPERSEDED` par ADR-014 (fichiers retirés de la branche et de son historique avant fusion)
- **Source** : message de l'opérateur du 2026-11-03, pour qu'Astra lise les résultats directement ; l'opérateur a été informé que le dépôt est **public** et que les journaux de décisions contiennent les bougies H4 et cotations EUR/USD 2015-2021 dérivées de Dukascopy (licence ambiguë, ASSUMP-018), et a choisi de tout publier, journaux compris.
- **Décision** : versionner, par ajout explicite (`git add -f`), les sorties des passages de référence (`s1_ref_2015_2021_*`) et de granularité (`s1_gran001_*`) de `data/reports/backtests/` : rapports JSON, journaux de décisions, journaux d'exécution, diffs de lancement, protocoles et comparaisons. La règle `data/` de `.gitignore` reste inchangée : historique de marché, Parquet et autres sorties ne sont pas versionnés.
- **Portée** : ces seuls fichiers. **Dérogation explicite** à ADR-004 (« données locales hors Git, jamais redistribuées ») pour ces données dérivées. Ne résout pas l'ambiguïté de licence (ASSUMP-018). En cas d'avertissement de Dukascopy, la purge devra aussi retirer ces fichiers du dépôt et de son historique ; `forex-history purge-dukascopy` ne le fait pas, et une publication sur un dépôt public peut avoir été copiée ou mise en cache entre-temps.

### ADR-013 : Expérience de risque à 1 % par opération sur 2015-2021
- **Date** : 2026-11-03
- **Statut** : `ACCEPTED` (décision de l'opérateur)
- **Source** : message de l'opérateur du 2026-11-03, après la revue par Astra du commit `d316d31`. La conclusion de l'expérience à 0,01 contrat (ADR-011) est retenue pour 2015-2021, sans nouveau passage.
- **Décision** : une variante unique rejoue toute la trajectoire 2015-2021 avec un risque de 1 % des fonds propres par opération au lieu de 0,25 % (budget initial 20 € au lieu de 5 €, recalculé à chaque décision), minimum et pas de 0,1 contrat comme la référence, tout le reste identique ; H1 ou rejet à l'exécution seulement si les cas se présentent. Protocole figé avant lancement : `docs/experiments/S1_RISK_1PCT_001.md`. Journaux détaillés conservés localement ; bilan agrégé pour la revue.
- **Portée** : backtest seulement. Pas de combinaison 1 % / 0,01 contrat, aucun ajustement après lecture des résultats, aucune donnée 2022-2025, aucun ordre ; ni validation de performance ni autorisation de trading.

### ADR-014 : Clôture de l'expérience à 1 % et contenu de la PR #5 dans `main`
- **Date** : 2026-11-03
- **Statut** : `ACCEPTED` (décision de l'opérateur)
- **Source** : messages de l'opérateur du 2026-11-03, après les résultats du test à 1 % (`docs/experiments/S1_RISK_1PCT_001.md`).
- **Décision** :
  1. L'expérience S1 à 1 % est close. S1 à 0,25 %, avec ses paramètres et coûts inchangés, reste la référence de développement. Aucune autre variante de risque n'est lancée.
  2. Entrent dans `main` : le code, les tests, les protocoles et les résultats agrégés (`docs/experiments/`, `.ai/`). Restent hors de la fusion les sorties de passage de `data/reports/backtests/` : journaux de décisions (bougies H4 et cotations), rapports et comparaisons (prix d'entrée, de sortie et de stop), qui sont dérivés de Dukascopy, ainsi que les journaux d'exécution, diffs de lancement et copies de protocole, qui suivent la règle `data/` du `.gitignore`.
  3. L'opérateur autorise la réécriture de l'historique public de la branche de la PR #5 et la fusion par l'agent. Le commit `d316d31`, seul à contenir ces fichiers, est retiré de la branche (rebase, poussée forcée) ; les fichiers restent sur le poste de l'opérateur, hors Git. ADR-012 est remplacée.
- **Portée** : la réécriture retire ces fichiers de la branche et de `main` ; elle ne garantit pas leur disparition des copies, caches ou références déjà créés par GitHub ou par des tiers pendant leur publication (ASSUMP-018 inchangée). Ni validation de performance ni autorisation de trading.

### ADR-015 : Approbation de S2 (ASSUMP-025) pour la recherche hors ligne
- **Date** : 2026-11-03
- **Statut** : `ACCEPTED` (décision de l'opérateur)
- **Source** : message de l'opérateur du 2026-11-03, après revue de la fiche `docs/strategies/S2_PULLBACK.md` au commit `a10a779` (PR #6).
- **Décision** : ASSUMP-025 est approuvée pour la recherche hors ligne, avec les paramètres de la fiche. Décisions sur les points ouverts : (1) la première cassure consomme le seuil, même si l'entrée est refusée ; une nouvelle tentative exige un nouveau pivot formé puis confirmé après ce refus ; (2) vente : structure et `E` sur le bid, stop sur l'extrême `ask_high` du repli, cible atteinte quand ask ≤ `E`, sans correction forfaitaire du spread ; (3) scénario C : sortie au niveau `E` comptabilisée au premier tick qui clôt le trou, intervalle du trou et instant de comptabilisation journalisés séparément, aucun capital libéré rétroactivement ; (4) un net strictement positif dans chaque scénario publié est un résultat favorable sur la période de développement ; un changement de signe entre A, B et C signifie que le résultat dépend du traitement des trous ; tous les résultats sont publiés ; le net sans la meilleure transaction reste un indicateur de concentration et 6 % un seuil de revue. Bornes temporelles explicites : `début(pivot) ≥ fin(contact)` et `confirmation(seuil) ≤ début(bougie de cassure)`, en H1 et en H4 ; la comparaison H4 compare deux séquences complètes.
- **Suite autorisée** : après fusion de la PR documentaire, étape 1 seulement (implémentation et tests synthétiques), sur une branche distincte. Le rejeu S1 sur 2019 (étape 2) n'est pas lancé ; aucun passage historique S2, aucune donnée 2022-2025, aucun entraînement, aucun ordre.

### ADR-016 : Bilan S2 2015-2021 validé, S2 étudiée sans conclusion
- **Date** : 2026-11-04
- **Statut** : `ACCEPTED` (décision de l'opérateur)
- **Source** : message de l'opérateur du 2026-11-04, après le bilan `docs/experiments/S2_REFERENCE_2015_2021_BILAN.md` (PR #9, `f71a1ac`).
- **Décision** : le bilan de l'étape 4 est validé. H1 reste la référence de S2, H4 la comparaison préenregistrée. Statut de S2 : **étudiée sur la partition de développement, résultats insuffisants pour conclure** (7 transactions, net dépendant d'une seule). Aucun paramètre n'est modifié ; B, C et le rejet à l'exécution ne sont pas lancés, leurs conditions (§4 du protocole) n'étant pas réunies. Avant fusion, le compteur annuel des cassures S2 suit la définition du compteur global, sans modification du rapport S1.
- **Suite autorisée** : fusion de la PR #9 après vérification, puis rédaction de la fiche S3 (cassure après compression de volatilité) depuis `main`, fiche seulement : ni implémentation, ni optimisation, ni entraînement, ni lecture de 2022-2025, ni ordre.

### ADR-017 : Étude descriptive de volatilité S2 validée ; sortie unique de la référence S3
- **Date** : 2026-11-04
- **Statut** : `ACCEPTED` (décision de l'opérateur)
- **Source** : message de l'opérateur du 2026-11-04, après l'étude `docs/experiments/S2_VOLATILITY_2015_2021.md` (PR #11).
- **Décision** :
  1. L'étude est validée ; S2 reste inchangée et aucun autre calcul S2 n'est demandé. Conclusion retenue : « Sur les 66 cassures EUR/USD étudiées, la cible et le stop sont plus éloignés dans le groupe le plus volatil, mais le rapport cible/stop ne s'améliore pas de façon régulière. » Elle ne prouve ni que la volatilité est sans effet, ni qu'une autre paire serait préférable.
  2. Fiche S3 (PR #10), première référence : une seule règle de sortie de stratégie, la sortie suiveuse sur clôture H4 de l'autre côté de la moyenne de Bollinger, en plus du stop garanti de protection. La première réintégration de la boîte est journalisée sans déclencher de sortie ; une version sortant à la réintégration relèverait d'un protocole séparé, comme le test de sensibilité (ni grille ni optimisation). D1 → H4 reste la référence, H4 sans filtre D1 la comparaison, une seule tentative par boîte.
- **Portée** : documentation seulement ; ASSUMP-026 reste `PROPOSED` jusqu'à revue du diff de la fiche. Aucune implémentation S3, aucun backtest, aucune donnée 2022-2025.

### ADR-018 : Approbation de S3 (ASSUMP-026) pour la recherche hors ligne
- **Date** : 2026-11-04
- **Statut** : `ACCEPTED` (décision de l'opérateur)
- **Source** : message de l'opérateur du 2026-11-04, après revue du diff de la fiche `docs/strategies/S3_SQUEEZE.md` (PR #10, `e826fd9`).
- **Décision** : ASSUMP-026 est approuvée pour la recherche hors ligne.
  1. *Paramètres* : valeurs du §10 conservées telles quelles, sans grille ni optimisation ; valeurs de référence de l'expérience, efficacité à mesurer.
  2. *Sorties* : ni cible ni sortie temporelle ; la moyenne de 20 H4 est la seule règle de sortie de stratégie et ne garantit aucune durée maximale ; le stop garanti simulé reste en place jusqu'à la sortie effective ; une position ouverte en fin d'étude est valorisée séparément, sans clôture fictive.
  3. *Annonces* : aucun filtre, faute de calendrier historique validé ; le stop garanti simulé ne mesure pas à lui seul les effets d'une annonce sur le spread ou le prix d'entrée.
  4. *Journal* : la première clôture de retour est une réintégration si `BL ≤ clôture bid ≤ BH` (bornes incluses), une traversée si elle passe directement au-delà de la borne opposée, à l'achat et à la vente ; aucun de ces événements ne provoque à lui seul une sortie ; si la même clôture déclenche la sortie suiveuse, l'observation et la décision sont conservées.
  Restent valables (ADR-017) : D1 → H4 en référence, H4 sans filtre D1 en comparaison, une seule tentative par boîte ; sortie sur réintégration et étude de sensibilité relèvent de protocoles séparés.
- **Suite autorisée** : fusion de la PR #10, puis étape 1 de S3 depuis `main` sur une branche distincte (moteur hors ligne et tests synthétiques uniquement). Aucun backtest historique, aucune donnée 2022-2025, aucun entraînement, aucun ordre.

### ADR-019 : Apprentissage par l'expérience, exigence future du cahier des charges (v1.2)
- **Date** : 2026-11-04
- **Statut** : `ACCEPTED` (décision de l'opérateur) — **exigence future, non implémentée**
- **Source** : message de l'opérateur du 2026-11-04 ; cahier des charges local mis à jour en v1.2 (hors dépôt, contenu non publié).
- **Décision** : le futur robot devra pouvoir examiner ses décisions, qualifier ce qui s'est passé (défaut de code ou de données, règle non respectée, perte normale, faiblesse hypothétique, indéterminé), formuler une hypothèse vérifiable, tester hors ligne des variantes ou des stratégies nouvelles dans un budget et sur des périodes autorisés à l'avance, les comparer à une référence identifiée dans les mêmes conditions et mémoriser chaque conclusion par identifiant, y compris quand la candidate fait moins bien. Modèles et orchestration locaux, sans API d'IA externe ; registre de recherche distinct de la bibliothèque autorisée ; l'agent de recherche ne peut ni envoyer d'ordre, ni modifier une stratégie active, ni assouplir le contrôleur de risque ; paper trading sur accord explicite de l'opérateur, réel par décision distincte. Réception : exemple synthétique complet, y compris une correction qui dégrade les résultats sans changer aucune stratégie active.
- **Portée** : spécification seulement. Aucun développement de l'agent de recherche n'est autorisé à ce stade ; périodes de validation et de test final inaccessibles pour multiplier les essais. Ne bloque pas les travaux S3.
