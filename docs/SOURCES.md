# Data sources and attribution

Source contracts were checked against official publisher pages on 2026-09-14. URLs and service
conditions can change, so recheck them before changing an adapter.

## DWD Climate Data Center

- Dataset: hourly station observations of 2 m air temperature and relative humidity.
- Historical Sprint 2 slice: Berlin-Tempelhof, station `00433`, recent rolling archive.
- Active Rhine–Ruhr profiles: Düsseldorf `01078`, Duisburg-Baerl `13670`, Essen-Bredeney
  `01303`, and Köln/Bonn `02667`.
- Format: ZIP containing a semicolon-delimited measurement table and metadata.
- Access: public HTTPS; no credentials.
- Quality note: DWD describes recent observations as not fully quality-controlled and subject to
  later change. SIGNAL//OPS preserves the source quality field and does not create a trust score.
- License: CC BY 4.0 under the DWD terms of use.

Official references:

- [Dataset directory](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/air_temperature/)
- [Recent station files](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/air_temperature/recent/)
- [Current hourly station catalogue](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/air_temperature/recent/TU_Stundenwerte_Beschreibung_Stationen.txt)
- [Dataset description](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/air_temperature/DESCRIPTION_obsgermany_climate_hourly_air_temperature_en.pdf)
- [DWD terms of use](https://opendata.dwd.de/climate_environment/CDC/Terms_of_use.txt)

Suggested attribution: Deutscher Wetterdienst (DWD), Climate Data Center (CDC), hourly station
observations of 2 m air temperature and humidity for Germany. Data may have been processed by
SIGNAL//OPS.

## Deutsche Bahn Timetables

- Dataset: planned and changed arrival/departure information for railway stations.
- Historical Sprint 2 slice: Berlin Hauptbahnhof, EVA `8011160`, one requested hour.
- Active station profiles verified through DB `GET /station/{pattern}`: Düsseldorf Hbf
  `8000085`, Duisburg Hbf `8000086`, Essen Hbf `8000098`, and Köln Hbf `8000207`.
- Format: XML.
- Access: a free DB API Marketplace subscription is available, but registration, an application,
  and credentials are required.
- Runtime headers: `DB-Client-Id` and `DB-Api-Key`; values remain outside Git.
- Published plan limit checked for Sprint 2: 60 calls per minute. SIGNAL//OPS makes one call per
  explicit DB ingestion command and implements no scheduler yet.
- License listed by DB: CC BY 4.0.
- Live access status: the configured application is subscribed and authenticated plan requests
  succeed. The first two Berlin plan responses were valid but empty XML.

Official references:

- [Timetables product](https://developers.deutschebahn.com/db-api-marketplace/apis/product/timetables)
- [Timetables API details](https://developers.deutschebahn.com/db-api-marketplace/apis/product/160163/api/160160)
- [DB API Marketplace getting started](https://developers.deutschebahn.com/db-api-marketplace/apis/start)
