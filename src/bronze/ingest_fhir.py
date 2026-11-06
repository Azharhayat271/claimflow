# Databricks notebook source
# Bronze FHIR ingest: every landed NDJSON line (one FHIR resource) becomes one row of bronze.fhir_raw.
# The resource is kept as raw JSON text; only its type and id are lifted out so silver can filter cheaply.
# Auto Loader checkpoints make re-runs load only new files.

# COMMAND ----------

from pyspark.sql import functions as F

dbutils.widgets.text("catalog", "claimflow")
dbutils.widgets.text("batch_id", "manual")
catalog = dbutils.widgets.get("catalog")
batch_id = dbutils.widgets.get("batch_id")

landing = f"/Volumes/{catalog}/bronze/landing/fhir"
state = f"/Volumes/{catalog}/bronze/checkpoints/fhir"
spark.sql(f"CREATE VOLUME IF NOT EXISTS {catalog}.bronze.checkpoints")

# COMMAND ----------

stream = (
    spark.readStream.format("cloudFiles")
    .option("cloudFiles.format", "text")
    .load(landing)
    .select(
        F.get_json_object("value", "$.resourceType").alias("resource_type"),
        F.get_json_object("value", "$.id").alias("resource_id"),
        F.col("value").alias("resource_json"),
        F.col("_metadata.file_path").alias("_source_file"),
        F.current_timestamp().alias("_ingested_at"),
        F.lit(batch_id).alias("_batch_id"),
    )
)
query = (
    stream.writeStream.option("checkpointLocation", f"{state}/checkpoint")
    .trigger(availableNow=True)
    .toTable(f"{catalog}.bronze.fhir_raw")
)
query.awaitTermination()

# COMMAND ----------

# Returned as the task output, so every run reports what it loaded.
import json

loaded_rows = {
    row["resource_type"]: row["count"]
    for row in spark.table(f"{catalog}.bronze.fhir_raw")
    .where(F.col("_batch_id") == batch_id)
    .groupBy("resource_type")
    .count()
    .collect()
}
dbutils.notebook.exit(json.dumps(loaded_rows))
