# imd-radiosondes

Daily record of every radiosonde flight the India Meteorological Department attempts,
including the ones that fail and the reason each failure is recorded against.

IMD's upper-air network releases balloons at around 04:30 and 16:30 IST from stations
across India, Lakshadweep, the Andamans and Antarctica. Each flight climbs for roughly an
hour and a half to about 30 km. This dataset covers the operation of those flights: when
the balloon went up, how long it flew, how high the instrument reported from, and what the
station recorded when nothing went up at all.

The source is a monitoring portal run by IMD's Upper Air Instruments Division. It is
public but undocumented, is not linked from IMD's main site, and publishes no
machine-readable format. Its archive reaches back to 2009.

## What one row means

One row of `ascents` is one station's attempt at one observation slot. A station that
flew appears with a release time, a duration, and the height and pressure at which its
instrument stopped reporting. A station that did not fly appears with those columns empty
and a reason in `misda_reason`, such as `NOINSTRUMENTS` when the station had no
radiosondes left or `NOCHEMICALS` when it had run out of the chemicals used to generate
lift gas.

Both kinds of row matter. The failure codes are the part of this record that exists
nowhere else.

## Data

| File | Contents |
| --- | --- |
| [`data/ascents.csv`](data/ascents.csv), [`.parquet`](data/ascents.parquet) | The flight record, one row per station and slot |
| [`data/consumables.csv`](data/consumables.csv), [`.parquet`](data/consumables.parquet) | Daily stock returns, one row per station and date |
| [`data/stations.csv`](data/stations.csv) | Station registry with coordinates and WMO numbers |
| [`data/stations.geojson`](data/stations.geojson) | The same stations as points |

See [`data/DATA.md`](data/DATA.md) for the schema, the failure codes and the conventions
the dataset follows.

Read the flight record with any Parquet reader:

```python
import polars as pl

ascents = pl.read_parquet("data/ascents.parquet")
failures = ascents.filter(~ascents["ascent_completed"])
```

## What this dataset is not

It holds no atmospheric measurements. There are no temperature, humidity or wind profiles
here, and no pressure levels. It records how each flight went, not what the flight
measured.

For the soundings themselves, use NOAA's
[Integrated Global Radiosonde Archive](https://www.ncei.noaa.gov/products/weather-balloon/integrated-global-radiosonde-archive),
which carries quality-controlled profiles for Indian stations back to 1926. The
`igra_id` column in `data/stations.csv` gives the identifier to look each station up by.

## Generate the dataset

Install [uv](https://docs.astral.sh/uv/), then:

```sh
uv sync
uv run python run.py update
```

`update` re-reads the last three days. The portal fills a slot in through the morning and
revises entries afterwards, so the most recent days are not final when first published and
re-reading them is what keeps the record correct.

To rebuild the archive from 2009:

```sh
uv run python run.py backfill
```

This issues roughly nineteen thousand requests against a small departmental server and
takes about ten hours. It keeps a courtesy delay between requests; leave it in place. The
run records each slot as it completes and skips slots it already holds, so an interrupted
backfill can be restarted with the same command.

`.github/workflows/update_dataset.yml` runs `update` daily at 04:00 UTC and commits what
changed.

## Limitations

The portal is undocumented. It carries no version, no schema and no stated retention
policy, and it can change or disappear without notice.

Coordinates, elevations and WMO numbers are not published by IMD. They come from NOAA's
IGRA station list, matched to IMD's station names, and three stations could not be
resolved. See the `stations` section of [`data/DATA.md`](data/DATA.md).

Ground equipment class cannot be backfilled. The portal reports it only for the most
recent slot and ignores any date asked of it.

The portal also publishes a page of stability indices computed by IMD, at
`ualAtmosphericIndices.php`. Every date tried returns column headings and no data, so
there is nothing to include and no index table is published here.

## Source

[Upper Air Observatory Monitoring System](https://ddgmui.imd.gov.in/ual), Upper Air
Instruments Division, India Meteorological Department.

Station coordinates come from the
[Integrated Global Radiosonde Archive](https://www.ncei.noaa.gov/pub/data/igra/) station
list, published by NOAA's National Centers for Environmental Information. An unmodified
copy is kept at `reference/igra2-station-list.txt`.

## License

Code is [MIT](LICENSE). Data is [ODbL 1.0](LICENSE-DATA).

The observations are published under the World Meteorological Organization's `core` data
policy, which places no restriction on their use or redistribution. Some individual
contents of the database are under copyright by the India Meteorological Department.

## AI declaration

Code and documentation in this repository were written with AI assistance.
