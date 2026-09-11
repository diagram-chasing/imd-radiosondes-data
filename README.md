# imd-radiosondes

A dataset of upper-air balloon flights from India Meteorological Department (IMD) stations. Each row records one station's ascent at one observation slot: release time, flight duration, maximum reported height, and IMD's reason code when the flight returned no data.

Coverage:

- 57 stations, across India, Lakshadweep, the Andaman Islands, and Antarctica.
- Two observation slots per day, at 00 UTC and 12 UTC.
- From 2009-01-01 to the present. A daily job appends new slots.

The data is scraped from the IMD Upper Air Instruments Division monitoring portal.

Browse the dataset at [diagram-chasing.github.io/imd-radiosondes-data](https://diagram-chasing.github.io/imd-radiosondes-data/).

## Data files

| File | Contents |
| --- | --- |
| [`data/ascents.csv`](data/ascents.csv), [`data/ascents.parquet`](data/ascents.parquet) | One row per station and observation slot |
| [`data/consumables.csv`](data/consumables.csv), [`data/consumables.parquet`](data/consumables.parquet) | One row per station and date: radiosondes, balloons, and other supplies in stock |
| [`data/stations.csv`](data/stations.csv) | One row per station: coordinates and WMO number |
| [`data/stations.geojson`](data/stations.geojson) | Stations with coordinates, as GeoJSON points |

Column definitions are in the [data dictionary](data/DATA.md).

## Build or update the dataset

Two commands scrape the portal: `backfill` builds the full archive, and `update` refreshes recent slots.

### Before you begin

1. Install [uv](https://docs.astral.sh/uv/).
2. Install dependencies:

   ```sh
   uv sync
   ```

### Build the full archive

```sh
uv run python run.py backfill
```

`backfill` covers every slot from 2009-01-01 to today, skipping any slot already in the dataset, so you can interrupt it and run it again.

### Update recent slots

```sh
uv run python run.py update
```

`update` re-scrapes the last three days, because a slot's report keeps changing for several hours after the portal first publishes it.

Both commands print the station registry, then one line per slot:

```
registry: 57 stations, 54 located
[1/6] 20260908-00: 39 rows, 31 completed
[2/6] 20260908-12: 30 rows, 21 completed
```

### Options

| Flag | Description |
| --- | --- |
| `--start DATE` | First observation date, in ISO format |
| `--days N` | Number of days to cover from the start date |
| `--limit N` | Stop after `N` observation slots |

## Sources

- Ascents and consumables: [IMD Upper Air Instruments Division monitoring portal](https://ddgmui.imd.gov.in/ual)
- Station coordinates and WMO numbers: [NOAA IGRA station list](https://www.ncei.noaa.gov/pub/data/igra/)

## License

Code: [MIT](LICENSE). Data: [Open Database License 1.0](LICENSE-DATA).

Under the ODbL, you can use, share, and adapt the data if you attribute the source and share derived databases under the same license. The observations are published under the World Meteorological Organization's core data policy, which places no restriction on their use or redistribution.

## AI declaration

Parts of this code and documentation were written with the help of Claude.
