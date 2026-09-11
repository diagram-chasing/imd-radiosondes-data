"""Monthly average stock of radiosondes and balloons at each station."""

import sys
from pathlib import Path

import polars as pl

DATA = Path(__file__).resolve().parents[3] / "data"

INSTRUMENTS = [
    "instruments_mk_3",
    "instruments_mk_4",
    "instruments_imdgps",
    "instruments_fgps",
    "instruments_others",
]
BALLOONS = ["balloons_pr875", "balloons_chinese", "balloons_others"]

supplies = (
    pl.scan_parquet(DATA / "consumables.parquet")
    .with_columns(
        month=pl.col("report_date").dt.truncate("1mo").cast(pl.Datetime("ms")),
        instruments=pl.sum_horizontal(INSTRUMENTS),
        balloons=pl.sum_horizontal(BALLOONS),
    )
    .group_by("station_name", "month")
    .agg(
        reports=pl.len(),
        instruments=pl.col("instruments").mean().round(0).cast(pl.Int64),
        balloons=pl.col("balloons").mean().round(0).cast(pl.Int64),
    )
    .sort("station_name", "month")
    .collect()
)

supplies.write_parquet(sys.stdout.buffer)
