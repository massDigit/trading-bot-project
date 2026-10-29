# DUKASCOPY_REQUEST.md - Question à Dukascopy (brouillon, NON ENVOYÉE)

> Préparée le 2026-10-27. À relire et envoyer **par l'opérateur uniquement**, s'il le décide.
> Destinataire probable : l'adresse indiquée dans la section 1 des « Terms of Use » de l'API JForex
> (demandes de licence), ou le support Dukascopy. Aucune donnée personnelle n'est incluse.
> Rédigée en anglais, langue des conditions citées.

---

**Subject:** JForex API – historical EUR/USD ticks for private backtesting: local storage and conversion

Hello,

I am an individual developing a private research and backtesting tool for my own trading. I would
like to retrieve historical EUR/USD tick data (bid/ask) through the JForex SDK (`IHistory.getTicks`),
and I want to make sure this falls within your terms before doing anything.

Intended use:
- private backtesting and research only, by me; no redistribution, publication, resale or display
  to third parties;
- initially one week (March 2019), later about 2015–2023, EUR/USD only;
- requests split by hour, at a moderate pace;
- the data would be stored **locally** on my computer, converted to Parquet files and aggregated
  into hourly, 4-hour and daily bid/ask candles; it may also be used to train a private model;
- research results may inform decisions on my own trading account held with **another broker**.

Relevant clauses:
- JForex API Terms of Use, Section 1: "personal, non-commercial […] temporary use of and access to
  the Dukascopy™ JForex API, all the images, materials, any other data or information it contains"
  and "Licensor reserves the right to define the limits of non-commercial use of Content".
- Section 2: "Licensee may not […] translate into another programming language, port, adapt,
  modify, […] store for commercial use any part of Content or any derivatives thereof".
- Website Terms of Use, Section 3: "The WEBSITE and the information contained therein may not be
  used to construct a database of any kind."

Questions:
1. Is the use described above "personal, non-commercial" use under the JForex API Terms of Use,
   including when results inform trading on an account held with another broker?
2. May I keep the retrieved ticks **persistently** on my computer, outside the JForex cache, and
   convert them into my own formats (Parquet files, aggregated candles) for private use only?
   Does the "temporary use" wording or the "adapt, modify" restriction prevent this?
3. Does the website clause on constructing a database apply to data retrieved through the JForex
   SDK, or to data exported manually with the Historical Data Export tool and stored locally?
4. Is a JForex demo account sufficient and permitted for retrieving historical data for this
   purpose? Are there request limits or recommended volumes for historical tick downloads?
5. Is the value returned by `ITick.getTime()` expressed in milliseconds since 1970-01-01 UTC?
   Is the `from` parameter of `IHistory.getTicks` inclusive, like `to`?
6. Is the "Powered by Dukascopy™" acknowledgement required for purely private use?
7. Is the full End User License Agreement mentioned in Section 1 available?

Thank you for your help.

---

## Après réponse

- Reporter chaque réponse dans `docs/DATA.md` (§1.3, §1.4) avec sa date et sa source.
- Une réponse partielle ou ambiguë laisse le point concerné **ouvert** ; aucune acquisition n'est
  faite sur la base d'une déduction.
