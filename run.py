"""Command line entry point for building and updating the dataset.

Two commands are available. `backfill` walks the portal's archive from 2009 forward and
skips any slot already recorded, so a run that is interrupted can be restarted where it
stopped. `update` re-fetches a short trailing window, which is what keeps the most recent
slots correct: the portal fills a slot in through the morning, so the first version of a
day's report is not its final one.

This is the only module that knows where the dataset is written or what state it keeps.
"""

import argparse
import json
from datetime import date, datetime, timedelta
from pathlib import Path

import polars as pl

import fetch
import parse
import stations

DATA = Path("data")
MANIFEST = DATA / "manifest.json"

# How many days back `update` re-reads. The 00 UTC report is still filling in during the
# Indian morning, and late corrections to the previous day are common.
UPDATE_DAYS = 3

# How many slots a backfill holds in memory before writing. See `_checkpoint`.
CHECKPOINT_SLOTS = 200

ASCENT_KEYS = ("observation_date", "observation_hour_utc", "station_name")
STOCK_KEYS = ("report_date", "station_name")

ASCENT_SCHEMA = {
    "observation_date": pl.Date,
    "observation_hour_utc": pl.Int8,
    "station_name": pl.String,
    "wmo_id": pl.Int64,
    "release_time_ist": pl.String,
    "release_time_utc": pl.Datetime("us"),
    "flight_duration_minutes": pl.Float64,
    "radiosonde_maximum_height_pressure_hpa": pl.Float64,
    "radiosonde_maximum_height_gpm": pl.Float64,
    "radiowind_maximum_height_pressure_hpa": pl.Float64,
    "radiowind_maximum_height_km": pl.Float64,
    "height_at_100_hpa_gpm": pl.Float64,
    "temperature_at_100_hpa_celsius": pl.Float64,
    "misda_reason": pl.String,
    "ascent_completed": pl.Boolean,
    "report_section": pl.String,
    "ground_equipment": pl.String,
}

STOCK_SCHEMA = {"report_date": pl.Date, "station_name": pl.String} | {
    column: pl.Int64 for column in parse.COMMODITY_COLUMNS
}


def load_manifest():
    """Reads the record of slots already fetched.

    Returns:
        A dictionary mapping a slot key to the time it was last fetched.
    """
    return json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}


def save_manifest(manifest):
    """Writes the record of slots already fetched.

    Args:
        manifest: The dictionary to write.
    """
    DATA.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=0, sort_keys=True))


def _upsert(frame, path, keys):
    """Merges rows into one Parquet partition, replacing any that share a key.

    Args:
        frame: The rows to write.
        path: The partition file.
        keys: The columns that identify a row.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        kept = pl.read_parquet(path).join(frame.select(keys).unique(),
                                          on=list(keys), how="anti")
        frame = pl.concat([kept, frame], how="diagonal")
    frame.sort(list(keys)).write_parquet(path)


def write_table(frame, name, keys):
    """Merges rows into a table and writes both of its published forms.

    Each table is one Parquet file and one CSV file. The CSV is written from the merged
    Parquet contents rather than maintained separately, so the two cannot drift apart.

    Args:
        frame: The rows to write.
        name: The table name, such as `ascents`.
        keys: The columns that identify a row.
    """
    path = DATA / f"{name}.parquet"
    _upsert(frame, path, keys)
    pl.read_parquet(path).write_csv(DATA / f"{name}.csv")


def _ascent_frame(records, registry, ground):
    """Assembles one slot's ascents into a typed frame.

    Args:
        records: Dictionaries returned by `parse.parse_flight_status`.
        registry: The station registry, used to attach WMO numbers.
        ground: The mapping returned by `parse.parse_ground_status`.

    Returns:
        A polars DataFrame matching `ASCENT_SCHEMA`.
    """
    for record in records:
        record["ground_equipment"] = ground.get(
            (record["station_name"], record["release_time_ist"])
        )
        record["wmo_id"] = registry.get(record["station_name"])
    return pl.DataFrame(records, schema=ASCENT_SCHEMA)


def _slots(start, end):
    """Lists every observation slot in a date range.

    Args:
        start: The first date, inclusive.
        end: The last date, inclusive.

    Yields:
        Tuples of `(date, hour)`.
    """
    day = start
    while day <= end:
        for hour in fetch.SLOTS:
            yield day, hour
        day += timedelta(days=1)


def run(start, end, limit, skip_recorded):
    """Fetches every slot in a date range and writes the result.

    Args:
        start: The first observation date, inclusive.
        end: The last observation date, inclusive.
        limit: If non-zero, stop after this many slots.
        skip_recorded: Whether to pass over slots already in the manifest.
    """
    client = fetch.new_client()
    manifest = load_manifest()

    roster = parse.parse_network_roster(fetch.network_roster(client))
    registry = stations.build_registry(roster, stations.read_igra_list())
    stations.write_stations(registry, DATA)
    wmo = dict(zip(registry["station_name"], registry["wmo_id"]))
    print(f"registry: {registry.height} stations, "
          f"{registry.filter(registry['latitude'].is_not_null()).height} located")

    # The ground equipment report is a live snapshot that ignores its date parameter, so
    # it is read once per run and matched to ascents by station and release time.
    try:
        ground = parse.parse_ground_status(fetch.ground_status(client))
    except RuntimeError as error:
        print(f"ground equipment: SKIPPED ({error})")
        ground = {}

    slots = list(_slots(start, end))
    if skip_recorded:
        slots = [s for s in slots if f"{s[0]:%Y%m%d}-{s[1]:02d}" not in manifest]
    if limit:
        slots = slots[:limit]

    ascents, stock, fetched = [], [], {}
    for index, (day, hour) in enumerate(slots, 1):
        key = f"{day:%Y%m%d}-{hour:02d}"
        try:
            records = parse.parse_flight_status(fetch.flight_status(client, day, hour),
                                                day, hour)
        except RuntimeError as error:
            print(f"[{index}/{len(slots)}] {key}: SKIPPED ({error})")
            continue

        if records:
            ascents.append(_ascent_frame(records, wmo, ground))
        flown = sum(r["ascent_completed"] for r in records)
        print(f"[{index}/{len(slots)}] {key}: {len(records)} ascents, {flown} flown")
        fetched[key] = datetime.now().isoformat(timespec="seconds")

        # Stock is reported once a day, not once a slot, so it is read on the first slot.
        if hour == fetch.SLOTS[0]:
            stock_key = f"{day:%Y%m%d}-stock"
            try:
                returns = parse.parse_consumable_stock(
                    fetch.consumable_stock(client, day), day)
            except RuntimeError as error:
                print(f"    stock {stock_key}: SKIPPED ({error})")
                returns = []
            if returns:
                stock.append(pl.DataFrame(returns, schema=STOCK_SCHEMA))
                fetched[stock_key] = datetime.now().isoformat(timespec="seconds")

        # Each table is a single file, so rewriting it after every slot would dominate a
        # long backfill. Rows are held until a checkpoint, and the manifest advances only
        # once they are on disk, so an interrupted run re-reads at most this many slots.
        if index % CHECKPOINT_SLOTS == 0:
            _checkpoint(ascents, stock, manifest, fetched)

    _checkpoint(ascents, stock, manifest, fetched)
    client.close()


def _checkpoint(ascents, stock, manifest, fetched):
    """Writes buffered rows to disk and records the slots they came from.

    Args:
        ascents: A list of ascent frames, emptied by this call.
        stock: A list of stock frames, emptied by this call.
        manifest: The manifest to update and save.
        fetched: Slot keys and fetch times to fold into the manifest, emptied by this
            call.
    """
    if ascents:
        write_table(pl.concat(ascents, how="diagonal"), "ascents", ASCENT_KEYS)
    if stock:
        write_table(pl.concat(stock, how="diagonal"), "consumables", STOCK_KEYS)
    if fetched:
        manifest.update(fetched)
        save_manifest(manifest)
    ascents.clear()
    stock.clear()
    fetched.clear()


def main():
    """Parses arguments and runs the requested command."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["backfill", "update"])
    parser.add_argument("--start", type=date.fromisoformat,
                        help="first observation date, ISO format")
    parser.add_argument("--days", type=int, default=0,
                        help="number of days to cover from the start date")
    parser.add_argument("--limit", type=int, default=0,
                        help="stop after this many observation slots")
    args = parser.parse_args()

    today = date.today()
    if args.command == "backfill":
        start = args.start or fetch.ARCHIVE_START
        end = start + timedelta(days=args.days - 1) if args.days else today
    else:
        days = args.days or UPDATE_DAYS
        start = args.start or today - timedelta(days=days - 1)
        end = min(start + timedelta(days=days - 1), today)

    run(start, min(end, today), args.limit, skip_recorded=args.command == "backfill")


if __name__ == "__main__":
    main()
