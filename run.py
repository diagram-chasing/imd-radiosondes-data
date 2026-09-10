"""Command line entry point for building and updating the dataset.

Run `backfill` to walk the portal's archive from 2009 forward. It skips any slot the
dataset already holds, so you can interrupt it and restart where it stopped. Run `update`
to re-read a short trailing window, which keeps the most recent slots accurate: the portal
fills a slot in through the Indian morning, so a day's first report is not its final one.

This module alone knows where the dataset lands and what state it keeps.
"""

import argparse
import json
from concurrent.futures import ThreadPoolExecutor
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

# The portal answers concurrent requests without slowing down, and its stock report takes
# about fifteen seconds a page, so reading one slot at a time would run for days. Six
# workers hold the combined rate below one request a second.
WORKERS = 6

# How recent a slot must be to take a ground equipment class from the live report. The
# report describes only the most recent slot, so attaching it to an older one would
# assert something the source never said.
GROUND_MATCH_DAYS = 1

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
    """Merges rows into a Parquet file, replacing any that share a key.

    Args:
        frame: The rows to write.
        path: The file to merge into.
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

    Each table is one Parquet file and one CSV file. This function writes the CSV from
    the merged Parquet contents rather than maintaining it separately, so the two cannot
    drift apart.

    Args:
        frame: The rows to write.
        name: The table name, such as `ascents`.
        keys: The columns that identify a row.
    """
    path = DATA / f"{name}.parquet"
    _upsert(frame, path, keys)
    pl.read_parquet(path).write_csv(DATA / f"{name}.csv")


def _ascent_frame(records, registry, ground, day):
    """Assembles one slot's ascents into a typed frame.

    Args:
        records: Dictionaries returned by `parse.parse_flight_status`.
        registry: Station names mapped to WMO numbers.
        ground: The mapping returned by `parse.parse_ground_status`.
        day: The observation date, used to decide whether the ground equipment report
            can describe this slot.

    Returns:
        A polars DataFrame matching `ASCENT_SCHEMA`.
    """
    recent = day >= date.today() - timedelta(days=GROUND_MATCH_DAYS)
    for record in records:
        record["ground_equipment"] = ground.get(
            (record["station_name"], record["release_time_ist"])) if recent else None
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

    # The ground equipment report ignores its date parameter and describes only the
    # latest slot, so read it once and match it to ascents by station and release time.
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
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        pages = pool.map(lambda slot: _read_slot(client, *slot), slots)
        for index, (day, hour, report, returns, error) in enumerate(pages, 1):
            key = f"{day:%Y%m%d}-{hour:02d}"
            if error is not None:
                print(f"[{index}/{len(slots)}] {key}: SKIPPED ({error})")
                continue

            records = parse.parse_flight_status(report, day, hour)
            if records:
                ascents.append(_ascent_frame(records, wmo, ground, day))
            flown = sum(r["ascent_completed"] for r in records)
            print(f"[{index}/{len(slots)}] {key}: {len(records)} ascents, {flown} flown")
            fetched[key] = datetime.now().isoformat(timespec="seconds")

            if returns is not None:
                rows = parse.parse_consumable_stock(returns, day)
                if rows:
                    stock.append(pl.DataFrame(rows, schema=STOCK_SCHEMA))
                    fetched[f"{day:%Y%m%d}-stock"] = fetched[key]

            # Each table is a single file, so rewriting it after every slot would
            # dominate a long backfill. The loop holds rows until a checkpoint and
            # advances the manifest only after they reach disk, so an interrupted run
            # re-reads at most this many slots.
            if index % CHECKPOINT_SLOTS == 0:
                _checkpoint(ascents, stock, manifest, fetched)

    _checkpoint(ascents, stock, manifest, fetched)
    client.close()


def _read_slot(client, day, hour):
    """Reads the reports one observation slot needs.

    The portal reports stock once a day rather than once a slot, so only the first slot of
    each day asks for it.

    Args:
        client: An open `httpx.Client`.
        day: A `datetime.date` naming the observation date in UTC.
        hour: The slot hour in UTC.

    Returns:
        A tuple of the date, the hour, the flight status markup, the stock markup or None,
        and the error that stopped the flight status request or None.
    """
    try:
        report = fetch.flight_status(client, day, hour)
    except RuntimeError as error:
        return day, hour, None, None, error
    returns = None
    if hour == fetch.SLOTS[0]:
        try:
            returns = fetch.consumable_stock(client, day)
        except RuntimeError as error:
            print(f"    stock {day:%Y%m%d}: SKIPPED ({error})")
    return day, hour, report, returns, None


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
