# Data dictionary

The dataset has three tables:

- `ascents`: one row per station and observation slot.
- `consumables`: one row per station and date of stock return.
- `stations`: one row per station, with coordinates and WMO number.

All dates and slot hours are UTC. Release times appear in both IST (as published by the source) and UTC.

## ascents

Files: `ascents.csv`, `ascents.parquet`.

| Column | Description |
| --- | --- |
| `observation_date` | Date of the observation slot (UTC) |
| `observation_hour_utc` | Slot hour: `0` or `12` |
| `station_name` | Station name as spelled by the source |
| `wmo_id` | WMO station number, if resolved |
| `release_time_ist` | Balloon release time, IST, as `HH:MM` |
| `release_time_utc` | Balloon release time, UTC, as `HH:MM` |
| `flight_duration_minutes` | Flight duration in minutes |
| `radiosonde_maximum_height_gpm` | Geopotential height of the last radiosonde report |
| `radiosonde_maximum_height_pressure_hpa` | Pressure at the last radiosonde report |
| `radiowind_maximum_height_km` | Height of the last wind measurement, in kilometres |
| `radiowind_maximum_height_pressure_hpa` | Pressure at the last wind measurement |
| `height_at_100_hpa_gpm` | Geopotential height of the 100 hPa surface |
| `temperature_at_100_hpa_celsius` | Temperature at 100 hPa, in degrees Celsius |
| `misda_reason` | Reason the ascent produced no data. `NONE` if the ascent produced data |
| `ascent_completed` | `true` if `misda_reason` is `NONE` |
| `report_section` | Section heading the source files the row under |
| `ground_equipment` | Class of ground receiving equipment, if known |

The maximum height columns record the last level each instrument reported.

### Missing values

The source writes `0.0` for any value it does not have. The dataset writes an empty cell instead.

**Caution:** If you read the portal directly, its zeros are missing values, not measurements.

A row with every measured column empty records an ascent that did not take place. For such rows, the source fills the release time with the slot's clock time. The dataset leaves `release_time_ist` and `release_time_utc` empty.

`release_time_utc` is a timezone conversion of `release_time_ist`. The source reports release times to the minute and rounds some of them.

### misda_reason

MISDA is the source's abbreviation for missing data.

| Code | Meaning |
| --- | --- |
| `NONE` | Ascent produced data; no failure recorded |
| `NIL` | Station filed no entry for the slot |
| `NOINSTRUMENTS` | No radiosondes in stock |
| `NOBALLOONS` | No balloons in stock |
| `NOCHEMICALS` | No lift-gas chemicals in stock |
| `NOBATTERIES` | No batteries in stock |
| `GNDEQUIPFAULT` | Ground receiving equipment fault |
| `SIGNALFAIL` | Instrument signal lost or never acquired |
| `METELEMENTFAIL` | Meteorological sensor failure on the instrument |
| `DATADOUBTFUL` | Ascent produced data the station did not trust |
| `ASCENTSUSPEND` | Ascents suspended at the station |
| `OTHERS` | Reason not stated by the source |

### report_section

The source groups stations under headings named for the pressure level the radiosonde reached.

| Code | Source heading |
| --- | --- |
| `ABOVE_10_HPA` | Above 10 hPa |
| `BETWEEN_20_AND_10_HPA` | Between 20 and 10 hPa |
| `BETWEEN_30_AND_20_HPA` | Between 30 and 20 hPa |
| `BETWEEN_100_AND_30_HPA` | Between 100 and 30 hPa |
| `BETWEEN_200_AND_100_HPA` | Between 200 and 100 hPa |
| `BELOW_200_HPA` | Less than 200 hPa |
| `MISDA_RADIOSONDE_AND_RADIOWIND` | MISDA [RS&RW] |
| `MISDA_RADIOWIND` | Radio Wind [RS-Misda] |

## consumables

Files: `consumables.csv`, `consumables.parquet`.

| Column | Description |
| --- | --- |
| `report_date` | Date of the stock return |
| `station_name` | Station name as spelled by the source |
| `instruments_mk_3` | Radiosondes, type Mk 3 |
| `instruments_mk_4` | Radiosondes, type Mk 4 |
| `instruments_imdgps` | Radiosondes, type IMDGPS |
| `instruments_fgps` | Radiosondes, type FGPS |
| `instruments_others` | Radiosondes, other types |
| `balloons_pr875` | Balloons, type PR875 |
| `balloons_chinese` | Balloons, type "Chinese" as named by the source |
| `balloons_others` | Balloons, other types |
| `thread` | Thread |
| `batteries` | Batteries |
| `targets` | Radar targets |
| `chemicals_caustic_soda` | Caustic soda |
| `chemicals_ferro_silicon` | Ferro silicon |

## stations

Files: `stations.csv`, and `stations.geojson` for stations with coordinates.

| Column | Description |
| --- | --- |
| `station_name` | Station name as spelled by the source. Join key to `ascents` |
| `wmo_id` | WMO station number |
| `igra_id` | Identifier in NOAA's Integrated Global Radiosonde Archive (IGRA) |
| `igra_name` | Station name as spelled by IGRA |
| `latitude` | Latitude in decimal degrees |
| `longitude` | Longitude in decimal degrees |
| `elevation_m` | Station elevation in metres |
| `in_network_roster` | `true` if the station appears in the source's network list |
