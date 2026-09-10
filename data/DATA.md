# Data dictionary

The dataset has three tables. `ascents` is the flight record, one row per station and
observation slot. `consumables` is the daily stock return, one row per station and date.
`stations` is the registry that gives each station a position.

Dates and slot hours are UTC. Release times appear both as the IST clock reading the
source publishes and as the UTC instant that reading corresponds to.

## ascents

One row per station and observation slot, in `ascents.csv` and `ascents.parquet`.

| Column | Description |
| --- | --- |
| `observation_date` | Date of the observation slot (UTC) |
| `observation_hour_utc` | Slot hour, `0` or `12` |
| `station_name` | Station name as the source publishes it |
| `wmo_id` | WMO station number, where the station could be resolved |
| `release_time_ist` | Balloon release clock time in IST, `HH:MM` |
| `release_time_utc` | The same release, converted to UTC |
| `flight_duration_minutes` | Duration of the ascent |
| `radiosonde_maximum_height_gpm` | Geopotential height of the last radiosonde report |
| `radiosonde_maximum_height_pressure_hpa` | Pressure at that height |
| `radiowind_maximum_height_km` | Height of the last wind measurement |
| `radiowind_maximum_height_pressure_hpa` | Pressure at that height |
| `height_at_100_hpa_gpm` | Geopotential height of the 100 hPa surface |
| `temperature_at_100_hpa_celsius` | Temperature at 100 hPa |
| `misda_reason` | Reason recorded against the ascent; `NONE` when it produced data |
| `ascent_completed` | `true` when `misda_reason` is `NONE` |
| `report_section` | The band the source files the row under |
| `ground_equipment` | Ground station class, where known |

The radiosonde and radiowind maximum heights are the last levels each instrument reported,
which for a completed flight is normally where the balloon burst. The source labels them
maximum height and this dataset keeps that label rather than asserting a burst.

## Empty cells

The source writes `0.0` rather than leaving a numeric cell blank. This dataset publishes
those as empty instead, because none of these quantities can legitimately be zero: an
ascent that reached zero geopotential metres did not happen, and the 100 hPa surface is
never at 0 degrees Celsius. Reading the source directly and taking the zeros at face value
will understate every height and overstate every temperature.

A row whose measured columns are all empty records an ascent that did not take place. In
those rows the source writes the slot's own clock time in the release column as a stand-in
for a blank, so `release_time_ist` and `release_time_utc` are empty as well. Those same
clock times are genuine elsewhere: Patiala released at 17:30 IST on 2026-09-10 and flew
for 105 minutes.

`release_time_utc` is a direct conversion of the clock reading, not an independent
observation. The source publishes release times to the minute and rounds some of them.

## misda_reason

MISDA is the source's abbreviation for missing data. A code outside this table is
published unchanged.

| Code | Meaning |
| --- | --- |
| `NONE` | The ascent produced data; no failure was recorded |
| `NIL` | No entry was filed for this station and slot |
| `NOINSTRUMENTS` | The station held no radiosondes |
| `NOBALLOONS` | The station held no balloons |
| `NOCHEMICALS` | The station held none of the chemicals used to generate lift gas |
| `NOBATTERIES` | The station held no batteries |
| `GNDEQUIPFAULT` | The ground receiving equipment was faulty |
| `SIGNALFAIL` | The instrument's signal was lost or never acquired |
| `METELEMENTFAIL` | A meteorological sensor on the instrument failed |
| `DATADOUBTFUL` | The ascent produced data the station did not trust |
| `ASCENTSUSPEND` | Ascents at this station were suspended |
| `OTHERS` | A reason outside the coded list, which the source does not state |

## report_section

The source groups its stations under headings that name the pressure the radiosonde
reached, so the heading doubles as its own classification of how far the ascent got.

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

## ground_equipment

The class of ground receiving equipment used for the ascent, such as `IMS` or `KORGPS`.

The source reports this only for the most recent slot and ignores any date asked of it, so
the column cannot be backfilled. It is empty for every slot that predates the start of
daily collection, and is filled going forward only where a station's name and release time
match the live report.

## consumables

One row per station and date, in `consumables.csv` and `consumables.parquet`.

| Column | Description |
| --- | --- |
| `report_date` | Date of the stock return |
| `station_name` | Station name as the source publishes it |
| `instruments_mk_3` | Radiosondes of type Mk 3 held |
| `instruments_mk_4` | Radiosondes of type Mk 4 held |
| `instruments_imdgps` | Radiosondes of type IMDGPS held |
| `instruments_fgps` | Radiosondes of type FGPS held |
| `instruments_others` | Radiosondes of other types held |
| `balloons_pr875` | Balloons of type PR875 held |
| `balloons_chinese` | Balloons of the type the source calls Chinese held |
| `balloons_others` | Balloons of other types held |
| `thread` | Thread held |
| `batteries` | Batteries held |
| `targets` | Radar targets held |
| `chemicals_caustic_soda` | Caustic soda held |
| `chemicals_ferro_silicon` | Ferro silicon held |

The instrument and balloon type names are the source's own. The source does not say what
they stand for and this dataset does not expand them.

A zero is a genuine return: a station holding no radiosondes is why the flight record
shows it failing every morning. A station that files no return at all is absent from the
table for that date rather than recorded as holding nothing.

The source states no unit. The figures are counts of items for instruments, balloons,
targets and batteries; thread and chemicals are counts of whatever unit the station issues
them in.

## stations

One row per station in the network roster, in `stations.csv`. The subset with coordinates
is also published as `stations.geojson`, a FeatureCollection of points.

| Column | Description |
| --- | --- |
| `station_name` | Station name as the source publishes it, and the key to `ascents` |
| `wmo_id` | WMO station number |
| `igra_id` | Identifier in NOAA's Integrated Global Radiosonde Archive |
| `igra_name` | The archive's spelling of the station name |
| `latitude`, `longitude` | Coordinates in decimal degrees |
| `elevation_m` | Station elevation in metres |
| `in_network_roster` | Whether the station appears in the source's network list |

Coordinates, elevation and WMO numbers are not published by the source. They come from
`reference/igra2-station-list.txt`, an unmodified copy of NOAA's station list, matched to
the source's station names. This is the only part of the dataset drawn from outside IMD.

Three stations have no coordinates. Dimapur and Maitri are absent from the archive
altogether; Maitri is IMD's Antarctic station. Kavali appears in the archive at longitude
0.008, which is in the Atlantic, so its coordinate is rejected and only its WMO number is
published.
