# Databricks notebook source
# Bronze CSV ingest: each landed dataset folder loads into its own append-only Delta table, <dataset>_raw.
# Columns stay as strings; typing happens in silver. Auto Loader checkpoints make re-runs load only new files.

# COMMAND ----------

from pyspark.sql import functions as F

dbutils.widgets.text("catalog", "claimflow")
dbutils.widgets.text("batch_id", "manual")
catalog = dbutils.widgets.get("catalog")
batch_id = dbutils.widgets.get("batch_id")

landing = f"/Volumes/{catalog}/bronze/landing/csv"
state = f"/Volumes/{catalog}/bronze/checkpoints/csv"
spark.sql(f"CREATE VOLUME IF NOT EXISTS {catalog}.bronze.checkpoints")

# COMMAND ----------

datasets = sorted(entry.name.rstrip("/") for entry in dbutils.fs.ls(landing) if entry.isDir())
loaded_rows = {}

for dataset in datasets:
    stream = (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "csv")
        .option("cloudFiles.schemaLocation", f"{state}/{dataset}/schema")
        .option("header", "true")
        .load(f"{landing}/{dataset}")
        .select(
            "*",
            F.col("_metadata.file_path").alias("_source_file"),
            F.current_timestamp().alias("_ingested_at"),
            F.lit(batch_id).alias("_batch_id"),
        )
    )
    query = (
        stream.writeStream.option("checkpointLocation", f"{state}/{dataset}/checkpoint")
        .trigger(availableNow=True)
        .toTable(f"{catalog}.bronze.{dataset}_raw")
    )
    query.awaitTermination()
    loaded_rows[f"{dataset}_raw"] = (
        spark.table(f"{catalog}.bronze.{dataset}_raw").where(F.col("_batch_id") == batch_id).count()
    )

# COMMAND ----------

# Returned as the task output, so every run reports what it loaded.
import json

dbutils.notebook.exit(json.dumps(loaded_rows))
