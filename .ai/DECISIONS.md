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

### ADR-020 : Bilan S3 2015-2021 validé, S3 étudiée sans conclusion de rentabilité
- **Date** : 2026-11-04
- **Statut** : `ACCEPTED` (décision de l'opérateur)
- **Source** : message de l'opérateur du 2026-11-04, après le bilan `docs/experiments/S3_REFERENCE_2015_2021_BILAN.md` (PR #16, passages A sur `15d2c83`).
- **Décision** : les résultats de l'étape 4 sont validés. S3 est **étudiée sur EUR/USD 2015-2021**. D1 → H4 reste la référence ; la variante H4 seule reste une comparaison. Effectif insuffisant pour conclure sur sa rentabilité (5 transactions, net de +5,62 € dépendant d'une seule). Faible apport observé par rapport à S1 selon le critère de chevauchement des pertes (4 pertes sur 4 simultanées à une perte S1). Aucun changement de paramètres ; aucun passage B ni rejet à ajouter, leurs conditions (§4 du protocole) n'étant pas réunies.
- **Bilan versionné** : agrégé seulement (totaux annuels, meilleur gain, net sans ce gain, chevauchements) ; le détail transaction par transaction reste dans les rapports locaux, hors Git. Les blocages des cassures sont comptés au premier motif, dans l'ordre du moteur (données D1, expansion, direction D1, marché, taille).
- **Suite autorisée** : fusion de la PR #16. Aucun rejeu, aucune nouvelle expérience ; 2022-2025 reste en réserve.

### ADR-021 : Lot de données M5/M15 2015-2021 clôturé ; conventions de qualité et d'interruption propres à DAY_01
- **Date** : 2026-11-05
- **Statut** : `ACCEPTED` (décision de l'opérateur)
- **Source** : messages de l'opérateur du 2026-11-05, après le bilan `docs/experiments/DATA_M5_M15_2015_2021_BILAN.md` (construction `36daea1`, recalcul DAY_01 `c0272cc`, PR #18).
- **Décision** :
  1. *Lot de données* : intégrité de la construction M5/M15 validée et lot clôturé, avec les limites documentées dans le bilan (jours fériés probables exclus, trou du 2015-05-06, ticks Dukascopy et non prix IG). ASSUMP-028 est **approuvée pour la recherche hors ligne**.
  2. *Qualité des bougies DAY_01* : M5 sans tick absente et non `OK`, sans comblement ni qualification de « marché calme » ; M15 dont un sous-créneau M5 prévu est sans tick valide non `OK`, OHLC observés conservés avec le motif précis ; interruption si le silence dépasse **strictement 5 minutes** d'ouverture prévue, pour les M5 et les M15 ; à la clôture, seule la durée déjà connue compte ; l'audit rétrospectif reste séparé.
  3. *Entrée encore en attente* : annulée dès qu'une interruption devient connue avant son exécution, y compris si le premier tick suivant la révèle (ce tick n'exécute pas) ; motif journalisé (`ENTRÉE_ANNULÉE_INTERRUPTION`), tentative consommée.
  4. *Position déjà exécutée* : même seuil, strictement supérieur à 5 minutes d'ouverture prévue ; un silence d'exactement 5 minutes ne le dépasse pas. Une interruption ne signifie pas qu'un stop ou une cible a été touché : la transaction est conservée, jamais supprimée ni annulée rétroactivement ; le trou est traité selon les scénarios A/B/C prévus pour les issues non observables et journalisé. Une fermeture connue reste distincte d'une interruption inexpliquée.
- **Portée** : conventions de recherche propres à DAY_01. Elles ne changent ni les ticks, ni les statuts H1/H4/D1 existants, ni l'ATR H4 déjà spécifié (qui garde ses règles et son seuil), ni les moteurs et références S1-S3. La référence d'audit à 10 minutes est conservée pour comparaison.
- **Suite autorisée** : fusion de la PR #18 après mise à jour de la fiche et contrôles.

### ADR-022 : Fiche DAY_01 figée (ASSUMP-027) pour la recherche hors ligne
- **Date** : 2026-11-05
- **Statut** : `ACCEPTED` (décision de l'opérateur, sous condition vérifiée)
- **Source** : message de l'opérateur du 2026-11-05 : figer ASSUMP-027 après vérification qu'aucun arbitrage n'est encore implicitement ouvert. Vérification faite sur la fiche entière : aucun arbitrage ne demande de décision (fiche §11).
- **Décision** : ASSUMP-027 est **approuvée pour la recherche hors ligne** ; `docs/strategies/DAY_01_LONDON_RANGE.md` est figée.
  1. Choix retenus explicitement par l'opérateur le 2026-11-05 : confirmation possible sur la M5 du contact ; `k = 1,5` sans filtre sur le rapport net ; validité de l'entrée de 5 minutes ; stop garanti simulé sans minimum IG confirmé, hypothèse qui ne valide pas son exécutabilité chez IG ; conventions de l'ADR-021.
  2. Les autres lignes du §11 sont retenues telles que proposées : valeurs choisies a priori, revues par l'opérateur au fil de trois révisions et fusionnées (PR #17), sans grille ni optimisation.
  3. Conséquences consignées, sans nouveau choix (fiche §4.5, exemple C) :
     - une bougie de confirmation `OK` à sa clôture exclut tout silence connu de plus de 5 minutes : le dernier tick avant `D` date donc de 5 minutes au plus, en référence M5 comme en variante M15 ; l'écart entre la cotation à `D` et l'exécution est au plus de 10 minutes dans les deux cas ;
     - sans tick admissible dans `]D, D + 5 min]`, le silence dépasse 5 minutes avant l'échéance si la dernière cotation est antérieure à `D` : l'issue est alors `ENTRÉE_ANNULÉE_INTERRUPTION`. `ENTRÉE_EXPIRÉE` ne survient que si une cotation est horodatée exactement à `D` (elle compte pour le silence sans exécuter l'ordre) et qu'aucun tick n'arrive jusqu'à `D + 5 min` inclus : le silence vaut alors exactement 5 minutes à l'échéance, sans dépasser le seuil (correction du 2026-11-05, avant toute implémentation : une première rédaction déclarait ce cas impossible).
- **Suite autorisée** : depuis `main`, sur une branche distincte, moteur DAY_01 hors ligne et tests synthétiques, en PR brouillon. Aucun passage historique DAY_01, aucun entraînement, aucune lecture de 2022-2025, aucun ordre.

### ADR-023 : Libellés de liquidation DAY_01 clarifiés, variante M15 implémentée
- **Date** : 2026-11-05
- **Statut** : `ACCEPTED` (décision de l'opérateur)
- **Source** : message de l'opérateur du 2026-11-05 sur la PR #19 : distinguer explicitement le délai après 16:00, la durée du silence et le motif de clôture ; clarifier ou renommer `LIQUIDATION_RETARDÉE` pour que son compteur corresponde exactement à sa définition, sans modifier les règles d'exécution ; compléter la variante préenregistrée « H4 → M15, retest et confirmation sur M15 » avec les paramètres approuvés.
- **Décision** :
  1. Chaque ordre de liquidation de 16:00 rapporte trois grandeurs distinctes : **délai après 16:00** (instant de clôture moins 16:00:00), **silence clos par le tick de clôture** (durée depuis le tick précédent, et sa nature selon le seuil DAY_01 : aucun, fermeture connue, interruption inexpliquée), **motif de clôture** (`LIQUIDATION_16H`, ou le stop ou la cible qui l'ont précédée sur le même tick, fiche §5 point 2).
  2. `LIQUIDATION_RETARDÉE` est renommé **`LIQUIDATION_APRÈS_INTERRUPTION`**. Définition, seule comptée sous ce libellé : la position est clôturée par l'ordre de 16:00 lui-même, au premier tick qui clôt un silence de strictement plus de 5 minutes d'ouverture prévue. Un délai sans interruption (silence de 5 minutes au plus, y compris un délai de 5 minutes après un tick exactement à 16:00) n'est pas compté ; un stop ou une cible qui précèdent la liquidation après une interruption non plus (motif de clôture propre).
  3. `NUIT_NON_PRÉVUE` : clôture sur une journée de cotation postérieure à celle de l'ordre, quel que soit le motif.
  4. Règles d'exécution inchangées : liquidation au premier tick strictement postérieur à 16:00, priorité stop, cible, liquidation (ASSUMP-024), scénarios A/B/C de l'ADR-021.
  5. Variante M15 : retest, invalidation, confirmation et stop lus sur M15, mêmes règles et même délai de 60 minutes (`K + 15 min ≤ D ≤ K + 60 min`), cotation à `D` dans la M15 de confirmation, validité de l'entrée de 5 minutes. Aucun paramètre nouveau ni modifié : seul le choix de l'unité (`Trigger.M5`, référence ; `Trigger.M15`, comparaison) est exposé.
- **Conséquence** : fiche §5 et §9 alignées sur le nouveau libellé, sans autre changement. Aucun passage historique, aucune lecture de 2022-2025.

### ADR-024 : DAY_01 étudiée, résultats défavorables sur 2015-2021, aucune trajectoire retenue
- **Date** : 2026-11-07
- **Statut** : `ACCEPTED` (décision de l'opérateur)
- **Source** : message de l'opérateur du 2026-11-07 sur la PR #21, après revue du bilan `docs/experiments/DAY01_REFERENCE_2015_2021_BILAN.md` (passages A M5 et M15 sur `3d38ad5`, contrôles conformes, B, C et rejet non requis).
- **Décision** :
  1. DAY_01 est **étudiée** : résultats défavorables sur 2015-2021 dans les conditions testées (règles de la fiche figée, capital et coûts de recherche figés, scénario A) : net −586,71 € en M5 (référence, 831 transactions), −289,12 € en M15 (comparaison, 736 transactions), sept années déficitaires dans les deux trajectoires.
  2. M5 reste la référence et M15 la comparaison. **Aucune des deux trajectoires n'est retenue** pour poursuivre vers le paper trading.
  3. Aucune sélection de M15 après coup, aucun changement de paramètre, aucun filtre tiré des sous-groupes positifs (jours, heures, sens, saisons).
- **Conséquence** : étape close, PR #21 fusionnée. Aucun nouveau passage DAY_01. La suite de la bibliothèque de stratégies fera l'objet d'une décision séparée ; aucune lecture de 2022-2025, aucun entraînement, aucun ordre.

### ADR-025 : D2 avant D3 ; rédaction de la fiche DAY_02 autorisée
- **Date** : 2026-11-07
- **Statut** : `ACCEPTED` (décision de l'opérateur)
- **Source** : message de l'opérateur du 2026-11-07, après la proposition de suite de la bibliothèque (cahier v1.2 §6.6, §15 lot 3B, §16 point 2).
- **Décision** :
  1. L'ordre du lot 3B est confirmé : **D2 avant D3** (S3 déjà étudiée, ADR-020).
  2. Rédaction de la fiche DAY_02 (continuation après impulsion et drapeau) autorisée, **documentation seulement**, en PR brouillon : définitions exécutables et objectives de l'impulsion, du drapeau et de la continuation ; chronologie et informations disponibles à chaque décision ; référence et comparaison plus simple justifiées par la logique de la stratégie ; conventions de DAY_01 non transposées automatiquement (techniques distinguées des choix de stratégie ; extension d'ADR-021 explicite et soumise à validation) ; conditions IG listées comme point ouvert distinct ; mesures descriptives de chevauchement avec les stratégies étudiées, notamment S2 ; héritage technique non figé. Toutes les nouvelles valeurs restent `PROPOSED` (ASSUMP-029).
- **Portée** : aucun moteur, aucune analyse historique, aucun backtest, aucun entraînement, aucune lecture de 2022-2025, aucun contact avec IG, aucun ordre. Pas de système de sélection, pas de nouvelle variante de S1, S2, S3 ou DAY_01.

### ADR-026 : Base de rédaction de DAY_02 et convention de qualité à 5 minutes étendue à DAY_02
- **Date** : 2026-11-07
- **Statut** : `ACCEPTED` (décision de l'opérateur), **ASSUMP-029 reste `PROPOSED`**
- **Source** : message de l'opérateur du 2026-11-07, après lecture de la fiche DAY_02 au commit `14b3283` (PR #23).
- **Décision** :
  1. Base de rédaction retenue (propositions de référence du §12 de la fiche) : H1 pour l'ATR, configuration M15, déclenchement M5 et comparaison M15, cible par projection, sortie temporelle de deux heures, horaires proposés, configurations successives, absence de filtre d'annonces. Ce sont des hypothèses de recherche, pas des paramètres démontrés optimaux.
  2. Principe retenu : la convention de qualité M5/M15 à 5 minutes (ADR-021) est étendue à DAY_02, avec contrôle de couverture sur sa fenêtre propre, sans changer les H1 ni leur convention.
  3. Corrections demandées avant validation : ordre des extrêmes (`o < p` strict, aucun ordre supposé dans une bougie) ; règle déterministe extension / profondeur / expiration, identique en M5 et en M15 ; convention explicite de l'étude de disponibilité sans ticks ni positions, sans égalité promise ni position fictive, mesures structurelles distinguées des mesures à `D` ; traduction opérationnelle de la limite de perte journalière du cahier (§8), dont l'omission n'est pas acquise ; précisions horaires (entrées après 15:00, position après 17:00, échéances simultanées).
- **Portée** : documentation seulement. Aucun moteur, aucune analyse historique, aucun backtest, aucune lecture de 2022-2025, aucun ordre.

### ADR-027 : DAY_02, chronologie et valeurs de référence retenues ; limites journalière et hebdomadaire non appliquées dans la référence isolée
- **Date** : 2026-11-07
- **Statut** : `ACCEPTED` (décision de l'opérateur), **ASSUMP-029 reste `PROPOSED`** jusqu'au gel de la fiche
- **Source** : message de l'opérateur du 2026-11-07, après lecture de la fiche DAY_02 au commit `de4379d` (PR #23).
- **Décision** :
  1. *Chronologie* : extrêmes sur toute la fenêtre, `o < p` strict ; `p = j` consigné comme **restriction supplémentaire choisie pour la référence**, non comme une conséquence de `o < p` ; invalidation prioritaire sur l'extension, avec l'ancien `E` et l'ancien `I` ; bougie d'extension exclue du décompte de pause ; invalidation prioritaire sur une sortie dans la même bougie ; échéance incluse, puis expiration sans lecture salvatrice d'une bougie postérieure ; `LIQUIDATION_17H` en cas d'égalité des échéances, sans double clôture.
  2. *Limites de risque* : la référence de recherche isolée DAY_02 **n'applique pas** les blocages journalier de 1 % et hebdomadaire de 2 % du cahier (§8). Leur simulation opérationnelle est reportée au compte partagé, où décisions, capital, exposition et protections seront évalués ensemble. **Dérogation explicite et limitée à cette étude hors ligne** : elle ne modifie pas les exigences du futur compte et n'autorise aucun trading. Aucune remise à zéro automatique n'est introduite ni présentée comme une revue humaine. Risque de 0,25 % par opération, dimensionnement, protections et sorties inchangés ; 6 % reste un seuil de revue rapporté, avec poursuite de la trajectoire. Aucune variante avec ou sans limites. Des franchissements décrits, s'il y en a, auront leur formule et leurs fenêtres fixées dans le protocole de performance et décriront la trajectoire sans blocage, pas celle d'une trajectoire bloquée.
  3. *Étude de disponibilité* : « parcours sans position », avec ses limites de comparabilité. Le contrôle par configuration vérifie le parcours depuis l'état de reprise fourni ; il ne vérifie pas à lui seul l'instant de reprise, qui est rapproché de la fin de configuration, de l'issue d'entrée non exécutée ou de la clôture de position qui l'autorise.
  4. *Valeurs* : valeurs de référence des lignes 12 à 23 du §12.2 de `de4379d` retenues, sans variantes supplémentaires ; EUR/USD seulement ; convention de qualité à cinq minutes étendue sans modification des H1 (ADR-026) ; décision séparée sur les conditions IG avant les passages de performance ; choix technique de réutilisation examiné avant l'implémentation.
- **Portée** : documentation seulement. Aucun moteur, aucune analyse historique, aucun backtest, aucune lecture de 2022-2025, aucun ordre. Le gel de la fiche reste soumis à validation.

### ADR-028 : Fiche DAY_02 figée (ASSUMP-029) pour la recherche hors ligne
- **Date** : 2026-11-07
- **Statut** : `ACCEPTED` (décision de l'opérateur)
- **Source** : message de l'opérateur du 2026-11-07 validant le gel de la fiche `docs/strategies/DAY_02_FLAG_CONTINUATION.md` sur la base du commit `a6ac8ef` (PR #23).
- **Décision** : ASSUMP-029 est **approuvée pour la recherche hors ligne seulement** ; la fiche DAY_02 est figée, avec une correction rédactionnelle du §3.1 (durée de l'impulsion alignée sur le §5.1 : 2 à 4 M15 à la reconnaissance, jusqu'à 6 après extension), sans changement de règle. Restent valables ADR-026 et ADR-027.
- **Portée** : la validation porte sur les règles de recherche, **ni sur leur rentabilité ni sur leur exécutabilité chez IG**. La décision sur les conditions IG reste prévue avant les passages de performance. Aucun moteur, aucune analyse historique, aucun backtest, aucun entraînement, aucune lecture de 2022-2025, aucun ordre.
- **Suite autorisée** : après fusion de la PR #23, proposition technique de réutilisation du code en lecture seule, présentée avant toute implémentation.

### ADR-029 : Moteur DAY_02 hors ligne et tests synthétiques autorisés
- **Date** : 2026-11-07
- **Statut** : `ACCEPTED` (décision de l'opérateur)
- **Source** : message de l'opérateur du 2026-11-07, après la proposition technique de réutilisation présentée après la fusion de la PR #23.
- **Décision** : `Day02Backtest` est construit sur `S1Backtest`, règles propres dans `backtest/day02.py`, **sans héritage depuis `Day01Backtest`** et **sans modification des modules existants** ; référence M5 et comparaison M15 conformes à la fiche figée. Précisions : la fonction commune sur bougies (`configuration_from`) assure la cohérence entre moteur, étude et contrôle, mais n'est pas une vérification indépendante : les tests la comparent à des attentes explicites ; causalité vérifiée (bougies et ticks postérieurs sans effet sur les événements déjà connaissables) ; reprises testées (abandon, refus à `D`, expiration ou annulation d'une entrée, clôture de position, y compris au milieu d'une M15) ; ATR H1 vérifié sur fixtures synthétiques (schéma, amorçage, H1 attendue absente ou inutilisable, fermeture connue, fenêtre d'impulsion exclue) ; frontières d'exécution couvertes (tick à `D`, validité de 5 min, silence exactement égal puis strictement supérieur à 5 min, échéances sans cotation, égalité des échéances).
- **Portée** : moteur et tests synthétiques seulement. Ni outil de disponibilité, ni passage historique, ni rejeu historique, ni entraînement, ni lecture de 2022-2025, ni ordre. Un changement partagé éventuel doit être présenté avant d'être réalisé.
