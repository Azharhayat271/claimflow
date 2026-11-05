# ClaimFlow

A synthetic healthcare billing and claims data platform, built on Databricks with a medallion lakehouse (bronze, silver, gold), dbt, streaming CDC from a Postgres billing service, and Unity Catalog governance over PHI.

Data is generated with [Synthea](https://github.com/synthetichealth/synthea). No real patient data is used anywhere in this project.

**Status:** Day 1 of 100. Workspace, catalog and repo set up.

## Layout

| Folder | What lives there |
| --- | --- |
| `src/` | PySpark jobs: bronze ingestion, silver conforming, gold star schema, streaming, embeddings |
| `resources/` | Databricks Asset Bundle job and pipeline definitions |
| `dbt/` | dbt project: staging, marts, snapshots, tests |
| `services/` | Billing API (the CDC source system) and the MCP server |
| `infra/` | Docker Compose for the local Kafka stack; Terraform for Azure |
| `docs/` | Design write-ups: bus matrix, ERD, tuning notes, failure modes, HIPAA controls |
