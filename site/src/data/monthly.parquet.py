"""Network-wide monthly summary of observation slots."""

import sys
from pathlib import Path

import polars as pl

DATA = Path(__file__).resolve().parents[3] / "data"

monthly = (
    pl.scan_parquet(DATA / "ascents.parquet")
    .with_columns(
        month=pl.col("observation_date").dt.truncate("1mo").cast(pl.Datetime("ms")),
        returned=pl.col("radiosonde_maximum_height_gpm").is_not_null(),
    )
    .group_by("month")
    .agg(
        slots=pl.len(),
        returned=pl.col("returned").sum(),
        stations=pl.col("station_name").n_unique(),
        height_p10=pl.col("radiosonde_maximum_height_gpm").quantile(0.1),
        height_median=pl.col("radiosonde_maximum_height_gpm").median(),
        height_p90=pl.col("radiosonde_maximum_height_gpm").quantile(0.9),
        duration_median=pl.col("flight_duration_minutes").median(),
    )
    .sort("month")
    .collect()
)

monthly.write_parquet(sys.stdout.buffer)
