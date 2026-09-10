# imd-radiosondes

A dataset of upper-air (radiosonde) flight records from India Meteorological Department (IMD) stations. Each record covers one station and one observation slot: release time, flight duration, maximum reported height, and the reason for any missing ascent.

The source is the IMD Upper Air Instruments Division monitoring portal. Records start in 2009. A daily job appends new observation slots.

## Data files

| File | Contents |
| --- | --- |
| [`data/ascents.csv`](data/ascents.csv), [`data/ascents.parquet`](data/ascents.parquet) | One row per station and observation slot |
| [`data/consumables.csv`](data/consumables.csv), [`data/consumables.parquet`](data/consumables.parquet) | One row per station and date of stock return |
| [`data/stations.csv`](data/stations.csv) | Station registry with coordinates and WMO numbers |
| [`data/stations.geojson`](data/stations.geojson) | Station registry as GeoJSON points |

For column definitions, failure codes, and missing-value conventions, see the [data dictionary](data/DATA.md).

## Update the dataset

### Before you begin

Install [uv](https://docs.astral.sh/uv/).

### Run an update

1. Install dependencies:

   ```sh
   uv sync
   ```

2. Fetch the most recent observation slots:

   ```sh
   uv run python run.py update
   ```

   The output lists the station registry, then one line per observation slot:

   ```
   registry: 57 stations, 54 located
   [1/6] 20260908-00: 39 ascents, 31 flown
   [2/6] 20260908-12: 30 ascents, 21 flown
   ```

`update` re-reads the last three days. To rebuild the full archive from 2009, run `backfill` instead. `backfill` skips slots the dataset already holds, so you can interrupt and restart it.

Options for both commands:

| Flag | Description |
| --- | --- |
| `--start DATE` | First observation date, in ISO format |
| `--days N` | Number of days to cover from the start date |
| `--limit N` | Stop after `N` observation slots |

## Sources

- Flight records and stock returns: IMD [Upper Air Observatory Monitoring System](https://ddgmui.imd.gov.in/ual)
- Station coordinates: NOAA [IGRA station list](https://www.ncei.noaa.gov/pub/data/igra/)

## License

Code: [MIT](LICENSE). Data: [Open Database License 1.0](LICENSE-DATA).

The World Meteorological Organization classifies these observations as core data with no restriction on use or redistribution. IMD holds copyright in some individual contents of the database.

## AI declaration

Parts of this code and documentation were written with the help of Claude.
