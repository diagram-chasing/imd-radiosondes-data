"""Monthly summary of observation slots for each station."""

import sys
from pathlib import Path

import polars as pl

DATA = Path(__file__).resolve().parents[3] / "data"

station_monthly = (
    pl.scan_parquet(DATA / "ascents.parquet")
    .with_columns(
        month=pl.col("observation_date").dt.truncate("1mo").cast(pl.Datetime("ms")),
        returned=pl.col("radiosonde_maximum_height_gpm").is_not_null(),
    )
    .group_by("station_name", "month")
    .agg(
        slots=pl.len(),
        returned=pl.col("returned").sum(),
        height_median=pl.col("radiosonde_maximum_height_gpm").median(),
    )
    .sort("station_name", "month")
    .collect()
)

station_monthly.write_parquet(sys.stdout.buffer)
