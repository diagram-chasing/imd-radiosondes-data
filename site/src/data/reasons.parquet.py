"""Monthly counts of the reason code IMD reports for each slot without data."""

import sys
from pathlib import Path

import polars as pl

DATA = Path(__file__).resolve().parents[3] / "data"

reasons = (
    pl.scan_parquet(DATA / "ascents.parquet")
    .filter(pl.col("radiosonde_maximum_height_gpm").is_null())
    .with_columns(
        month=pl.col("observation_date").dt.truncate("1mo").cast(pl.Datetime("ms")),
        misda_reason=pl.when(pl.col("misda_reason") == "NONE")
        .then(pl.lit("NOT STATED"))
        .otherwise(pl.col("misda_reason")),
    )
    .group_by("month", "misda_reason")
    .agg(slots=pl.len())
    .sort("month", "misda_reason")
    .collect()
)

reasons.write_parquet(sys.stdout.buffer)
