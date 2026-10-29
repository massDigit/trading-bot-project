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
