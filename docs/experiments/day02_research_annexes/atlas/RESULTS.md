# Atlas EUR/USD 2015-2019 — résultats (2026-11-17)

Protocole : `PROTOCOL.md` (48 tests, BH 10 %, seuils fixés avant calcul). Script : `atlas.py` ;
détail : `results.json`. 2020+ non lu.

## Candidats (critères du protocole)
| Test | n | Moyenne (pips) | t | Années même signe | Par année 2015…2019 |
|---|---:|---:|---:|---|---|
| T1 09:00 → 13:00 Londres | 1 296 | −3,46 | −5,08 | 5/5 | −4,41 −3,79 −3,27 −3,29 −2,53 |
| T1 11:00 → 13:00 Londres | 1 296 | −2,55 | −5,35 | 5/5 | −2,30 −4,22 −2,12 −1,92 −2,17 |
| T2 mercredi 07:00-12:00 | 259 | −4,84 | −3,06 | 5/5 | −9,90 −3,78 −5,28 −3,86 −1,32 |

Significatifs après correction mais sous 2 pips : 08:00 +4 h (−1,92), 11:00 +1 h (−1,07), 12:00 +1 h (−1,48).

## Lecture
- Une seule régularité : **l'euro baisse face au dollar en matinée européenne, surtout 09:00-13:00
  Londres** (Breedon-Ranaldo). Les candidats T1 se recouvrent (même phénomène).
- Pas une dérive : en 2017 l'EUR/USD a monté de ~1 480 pips (+5,7 pips/jour ouvré), et 09:00-13:00 est
  pourtant à −3,27 pips en moyenne.
- Mercredi : la moyenne des cinq jours en 07:00-12:00 est d'environ −2,4 pips ; l'excès propre au mercredi
  (≈ −2,5 pips, ET ≈ 1,6) n'est pas significatif seul : probablement le même effet, pas un effet du jour.
- Après-midi américain (13:00 +1 à +4 h) positif mais non significatif.
- Sans effet exploitable : fin de mois, cassure de la veille (+1,24 pip à 1 h, non significatif après
  correction), cassure du range asiatique (−1,25 pip à 2 h, idem), momentum (première heure, nuit, veille).
- Ordre de grandeur brut : −3,46 pips sur 4 h ≈ 2,7 pips après aller-retour (≈ 0,8 pip), soit ≈ +0,12 R
  pour un stop de 20 pips, une transaction par jour, avant prime de stop et effet du stop sur la
  distribution. Mesuré sur les années de découverte : à confirmer sur 2020-2021 sans retouche.
