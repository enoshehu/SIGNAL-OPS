# Power BI version 1.0 handoff

Use `rail_snapshot.csv` only as the initial layout source. It reproduces the measured one-slice
railway evidence in the regional data profile; it contains no Weather × Railway finding because
there are zero paired hours.

The final report has three pages:

1. Railway overview: plans, matched changes, cancellations, positive delays, and city comparison.
2. Weather × Railway: temperature/humidity groups, paired hours, matched event counts, and visible
   caveats. Keep this page in a waiting state until paired evidence exists.
3. Data quality: source freshness, rule status, failed records, and latest retrieval time.

Do not calculate an overall trust score. Do not show unmatched change events as on-time services.
Export the completed report to PDF or screenshots so it remains reviewable without Power BI.
