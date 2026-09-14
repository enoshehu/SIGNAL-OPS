# Data sources and attribution

Source contracts were checked against official publisher pages on 2026-09-14. URLs and service
conditions can change, so recheck them before changing an adapter.

## DWD Climate Data Center

SIGNAL//OPS uses two complementary official DWD deliveries. The public POI station feed supplies
the rolling current 24-hour window, while CDC recent archives supply retained and finalized
history. Neither requires an API key.

### Current POI observations

- Format: semicolon-delimited CSV, one station per file, updated throughout the current day.
- Metrics: 2 m temperature, relative humidity, last-hour precipitation, 10-minute mean wind speed
  and direction, and maximum wind speed during the last hour (gust).
- Wind speed and gust arrive in km/h and are converted to m/s during parsing.
- Station mappings: Düsseldorf `10400`, Duisburg-Baerl `H419`, Essen `10410`, Köln/Bonn `10513`.
- POI readings are marked provisional in preserved source payloads. When an hour later exists in a
  CDC archive, the canonical city-hour export prefers the CDC value.

Official POI directory: https://opendata.dwd.de/weather/weather_reports/poi/

### CDC archives

- Dataset: hourly station observations of 2 m air temperature and relative humidity.
- Historical Sprint 2 slice: Berlin-Tempelhof, station `00433`, recent rolling archive.
- Active Rhine–Ruhr profiles: Düsseldorf `01078`, Duisburg-Baerl `13670`, Essen-Bredeney
  `01303`, and Köln/Bonn `02667`.
- Format: ZIP containing a semicolon-delimited measurement table and metadata.
- Access: public HTTPS; no credentials.
- Quality note: DWD describes recent observations as not fully quality-controlled and subject to
  later change. SIGNAL//OPS preserves the source quality field and does not create a trust score.
- License: CC BY 4.0 under the DWD terms of use.

### Additional version 1 weather products

- Hourly precipitation uses DWD's `R1` hourly total in millimetres. All four city weather stations
  publish this product.
- Hourly wind uses DWD's `F` mean speed and `D` direction. Düsseldorf, Essen, and Köln use their
  city weather station. Duisburg uses Xanten, approximately 26.5 km from Duisburg-Baerl, because
  Baerl has no active hourly-wind product.
- Hourly gust uses the extreme-wind product's `FX_911` maximum in metres per second. It follows
  the same station/proxy mapping as the CDC wind product.
- Rain at 1 mm/hour and wind at 10 m/s are transparent descriptive bands, not causal thresholds.
- Recent product rows are bounded to 180 days in the operational database; replayable raw files
  are bounded to 30 days to keep the rolling GitHub release asset manageable.

Official references:

- [Dataset directory](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/air_temperature/)
- [Recent station files](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/air_temperature/recent/)
- [Current hourly station catalogue](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/air_temperature/recent/TU_Stundenwerte_Beschreibung_Stationen.txt)
- [Dataset description](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/air_temperature/DESCRIPTION_obsgermany_climate_hourly_air_temperature_en.pdf)
- [Precipitation description](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/precipitation/DESCRIPTION_obsgermany_climate_hourly_precipitation_en.pdf)
- [Wind description](https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/wind/DESCRIPTION_obsgermany_climate_hourly_wind_en.pdf)
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
- Published plan limit checked for Sprint 2: 60 calls per minute. SIGNAL//OPS isolates calls by
  station and feed and schedules only streams whose refresh interval is due.
- License listed by DB: CC BY 4.0.
- Live access status: the configured application is subscribed; authenticated `plan` and `fchg`
  requests succeed. `fchg` is the full-change feed used for changed times and cancellations.
- Merge note: most change events do not repeat their planned time. SIGNAL//OPS therefore matches
  plan and change rows by station, DB stop ID, and arrival/departure type.

Official references:

- [Timetables product](https://developers.deutschebahn.com/db-api-marketplace/apis/product/timetables)
- [Timetables API details](https://developers.deutschebahn.com/db-api-marketplace/apis/product/160163/api/160160)
- [DB API Marketplace getting started](https://developers.deutschebahn.com/db-api-marketplace/apis/start)
