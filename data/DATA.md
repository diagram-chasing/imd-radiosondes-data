# Data dictionary

Terms used throughout:

- **Observation slot**: one of the two daily launch windows, at 00 UTC and 12 UTC.
- **Ascent**: one station's balloon flight for one slot. A row exists whether or not the balloon flew.
- **Completed ascent**: a row whose `misda_reason` is `NONE`.
- **MISDA**: IMD's abbreviation for missing data.
- **RS**, **RW**: IMD's abbreviations for radiosonde (the instrument package) and radiowind (the wind-tracking observation).
- **Stock report**: IMD's daily count of supplies held at each station.
- **Portal**: the IMD monitoring website that the dataset is scraped from.

All dates and slot hours are UTC. Release times are given in IST, as the portal reports them, and in UTC.

## ascents

Files: `ascents.csv`, `ascents.parquet`. One row per station and observation slot.

| Column | Description |
| --- | --- |
| `observation_date` | Date of the observation slot (UTC) |
| `observation_hour_utc` | Slot hour: `0` or `12` |
| `station_name` | Station name as spelled on the portal |
| `wmo_id` | WMO station number from the `stations` table, or blank if the station has no match there |
| `release_time_ist` | Balloon release time in IST, as `HH:MM` |
| `release_time_utc` | Balloon release time in UTC |
| `flight_duration_minutes` | Flight duration in minutes |
| `radiosonde_maximum_height_pressure_hpa` | Pressure at the last radiosonde report |
| `radiosonde_maximum_height_gpm` | Geopotential height of the last radiosonde report |
| `radiowind_maximum_height_pressure_hpa` | Pressure at the last radiowind report |
| `radiowind_maximum_height_km` | Height of the last radiowind report, in kilometres |
| `height_at_100_hpa_gpm` | Geopotential height of the 100 hPa surface |
| `temperature_at_100_hpa_celsius` | Temperature at 100 hPa, in degrees Celsius |
| `misda_reason` | The portal's reason code for the ascent. See [misda_reason](#misda_reason) |
| `ascent_completed` | `true` if `misda_reason` is `NONE` |
| `report_section` | The portal's section heading for this row. See [report_section](#report_section) |
| `ground_equipment` | Class of ground receiving equipment, such as `IMS` or `KORGPS`. Because the portal reports this for the latest slot only, it is filled only for rows scraped within a day of the slot |

### Missing values

The portal shows `0.0` wherever it has no value, so those cells are blank here.

A row with every measurement blank is a slot for which the portal reported no flight data. On such rows the portal shows the slot's launch window in the release time column as a placeholder, so the release time is blank here as well.

### misda_reason

Every row carries a reason code from the portal, copied as is. IMD does not publish definitions for these codes, so none are given here.

Rows outside the two MISDA sections always carry `NONE`. Codes seen so far:

`ASCENTSUSPEND`, `DATADOUBTFUL`, `GNDEQUIPFAULT`, `METELEMENTFAIL`, `NIL`, `NOBALLOONS`, `NOCHEMICALS`, `NOINSTRUMENTS`, `NONE`, `NOREFERENCE`, `OTHERS`, `SIGNALFAIL`

**Note:** Some rows in the MISDA sections also carry `NONE`, so `ascent_completed` is `true` for them even though they have no radiosonde measurements. To select ascents with radiosonde data, filter on `radiosonde_maximum_height_gpm` instead.

### report_section

The portal groups rows under headings named for the pressure at which the radiosonde stopped reporting. Because pressure falls with height, the first heading holds the highest ascents and `Less than 200 hPa` the lowest.

| Code | Portal heading |
| --- | --- |
| `ABOVE_10_HPA` | Above 10 hPa |
| `BETWEEN_20_AND_10_HPA` | Between 20 and 10 hPa |
| `BETWEEN_30_AND_20_HPA` | Between 30 and 20 hPa |
| `BETWEEN_100_AND_30_HPA` | Between 100 and 30 hPa |
| `BETWEEN_200_AND_100_HPA` | Between 200 and 100 hPa |
| `BELOW_200_HPA` | Less than 200 hPa |
| `MISDA_RADIOSONDE_AND_RADIOWIND` | MISDA [RS&RW] |
| `MISDA_RADIOWIND` | Radio Wind [RS-Misda] |

The bracketed text in the last two headings names the instruments involved but not which one failed, so the codes reproduce the heading rather than interpret it.

## consumables

Files: `consumables.csv`, `consumables.parquet`. One row per station and stock report date.

Each figure is the integer quantity the station reported in stock on that date. IMD gives no units and no definitions for the type names, so none are given here.

| Column | Description |
| --- | --- |
| `report_date` | Date of the stock report |
| `station_name` | Station name as spelled on the portal |
| `instruments_mk_3` | Radiosondes of type Mk 3 |
| `instruments_mk_4` | Radiosondes of type Mk 4 |
| `instruments_imdgps` | Radiosondes of type IMDGPS |
| `instruments_fgps` | Radiosondes of type FGPS |
| `instruments_others` | Radiosondes of any other type |
| `balloons_pr875` | Balloons of type PR875 |
| `balloons_chinese` | Balloons of the type the portal labels Chinese |
| `balloons_others` | Balloons of any other type |
| `thread` | Thread |
| `batteries` | Batteries |
| `targets` | Radar targets |
| `chemicals_caustic_soda` | Caustic soda |
| `chemicals_ferro_silicon` | Ferro silicon |

A zero is a reported quantity, whereas a station that filed no stock report for a date has no row for that date.

## stations

Files: `stations.csv`, and `stations.geojson` for the stations that have coordinates. One row per station in the portal's network roster.

Because the portal publishes station names only, the coordinates, elevation, and WMO numbers are taken from `reference/igra2-station-list.txt`, an unmodified copy of the NOAA Integrated Global Radiosonde Archive (IGRA) station list, matched on station name. This is the only table with data from outside IMD.

| Column | Description |
| --- | --- |
| `station_name` | Station name as spelled on the portal. Join key to `ascents` and `consumables` |
| `wmo_id` | WMO station number |
| `igra_id` | IGRA station identifier |
| `igra_name` | Station name as spelled by IGRA |
| `latitude` | Latitude in decimal degrees |
| `longitude` | Longitude in decimal degrees |
| `elevation_m` | Station elevation in metres |
| `in_network_roster` | `true` if the station appears in the portal's network roster |

Three stations have no coordinates:

- **Dimapur**: not in IGRA.
- **Maitri** (Antarctica): not in IGRA.
- **Kavali**: IGRA lists longitude 0.008, which is wrong, so only the WMO number is kept.
