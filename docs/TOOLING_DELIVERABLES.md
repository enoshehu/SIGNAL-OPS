# External-tool deliverables

These are optional review outputs, not application dependencies. Links are added only after an
artifact exists. Tokens and private workspace identifiers do not belong in this repository.

## Jira

- Four delivery epics: pipeline, data quality, analytics, and release.
- One controlled incident: `DWD schema change detected`.
- Required fields: source, severity, detected time, failed run, evidence, owner, status, resolution.
- Automation must suppress duplicate open incidents.
- Status: an importable starter backlog exists at `integrations/jira/version-1-backlog.csv`;
  the external project is not yet created.

## Confluence

- One architecture page linking back to repository definitions.
- One incident decision record for the controlled schema-change exercise.
- Export both pages to PDF for durable portfolio evidence.
- Status: the page source exists at `integrations/confluence/architecture-and-incident.md`;
  the external space is not yet created.

## Miro

- One board with four frames: architecture, data lineage, incident lifecycle, source onboarding.
- Export the board to PDF or images and keep the export in the release evidence.
- Status: the four-frame blueprint exists at `integrations/miro/board-blueprint.md`; the external
  board is not yet created.

## Power BI

- Page 1: four-city railway overview.
- Page 2: Weather × Railway investigation with sample size and caveats visible.
- Page 3: source freshness and data-quality results.
- Use only published versioned CSV files. Keep the `.pbix`, PDF/screenshots, field definitions,
  and refresh instructions together.
- Status: the initial dataset and report contract exist under `integrations/power-bi/`; creating
  the report requires Power BI Desktop or Service access.

## Excel

- One Data Steward Review Queue workbook.
- Required columns: record, dataset, city, problem, proposed action, reviewer, status.
- Version 1.0 exports review items but does not import reviewer edits.
- Status: initial workbook is stored at `artifacts/data_steward_review_queue.xlsx`.
