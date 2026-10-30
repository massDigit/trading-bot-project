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
