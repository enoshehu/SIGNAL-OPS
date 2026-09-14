# Five-minute demo script

1. Open the dashboard and explain the rule: same configured city and UTC hour, or no relationship
   claim.
2. Show the four city scopes and the explicit coverage notice.
3. Open one raw file and metadata sidecar to show source URL, retrieval time and SHA-256 lineage.
4. Run `signalops sync --dry-run` to show independent refresh clocks without making requests.
5. Show SQLite observations for temperature, humidity, precipitation and wind, then railway plans
   and changes.
6. Open the generated paired-window profile and point to sample sizes, missingness and limitations.
7. Run the controlled failure drill: corrupt input is retained, rejected before import, and recovered
   through a verified replay.
8. Finish with the GitHub workflow: 15-minute scheduling, seven-day retention, replacement release
   asset, Pages deployment and duplicate-safe failure issue.

Do not claim that weather causes disruption. Until paired evidence exists, explicitly say that the
system is collecting the necessary window and that the analytical result is pending.
