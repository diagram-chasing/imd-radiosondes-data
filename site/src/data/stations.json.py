"""Station roster with coordinates and a summary of each station's record."""

import json
import sys
from datetime import timedelta
from pathlib import Path

import polars as pl

DATA = Path(__file__).resolve().parents[3] / "data"

ascents = pl.read_parquet(
    DATA / "ascents.parquet",
    columns=["observation_date", "station_name", "radiosonde_maximum_height_gpm"],
).with_columns(returned=pl.col("radiosonde_maximum_height_gpm").is_not_null())

recent_from = ascents["observation_date"].max() - timedelta(days=365)

summary = (
    ascents.group_by("station_name")
    .agg(
        first_date=pl.col("observation_date").min(),
        last_date=pl.col("observation_date").max(),
        slots=pl.len(),
        returned=pl.col("returned").sum(),
        slots_recent=(pl.col("observation_date") >= recent_from).sum(),
        returned_recent=pl.col("returned")
        .filter(pl.col("observation_date") >= recent_from)
        .sum(),
        height_median=pl.col("radiosonde_maximum_height_gpm").median(),
    )
    .with_columns(
        first_date=pl.col("first_date").cast(pl.Utf8),
        last_date=pl.col("last_date").cast(pl.Utf8),
    )
)

stations = (
    pl.read_csv(DATA / "stations.csv")
    .join(summary, on="station_name", how="full", coalesce=True)
    .with_columns(
        in_network_roster=pl.col("in_network_roster").fill_null(False),
        slots=pl.col("slots").fill_null(0),
        returned=pl.col("returned").fill_null(0),
        slots_recent=pl.col("slots_recent").fill_null(0),
        returned_recent=pl.col("returned_recent").fill_null(0),
    )
    # IGRA writes -999.9 where it has no elevation.
    .with_columns(
        elevation_m=pl.when(pl.col("elevation_m") > -998)
        .then(pl.col("elevation_m"))
        .otherwise(None)
    )
    .drop("igra_id", "igra_name")
    .sort("station_name")
)

json.dump(stations.to_dicts(), sys.stdout)
