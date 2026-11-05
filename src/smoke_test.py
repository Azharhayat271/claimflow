# Databricks notebook source
# Smoke test: fails the job if the medallion schemas are missing from the catalog.

# COMMAND ----------

dbutils.widgets.text("catalog", "claimflow")
catalog = dbutils.widgets.get("catalog")

schemas = {row[0] for row in spark.sql(f"SHOW SCHEMAS IN {catalog}").collect()}
print(f"Schemas in {catalog}: {sorted(schemas)}")

missing = {"bronze", "silver", "gold"} - schemas
assert not missing, f"Missing schemas in {catalog}: {sorted(missing)}"
print("Smoke test passed")
