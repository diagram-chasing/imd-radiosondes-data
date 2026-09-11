"""Interpretation of the upper-air monitoring portal's HTML report tables.

The portal publishes no machine-readable format, so every report is read out of its
markup. Each function here takes the text returned by a `fetch` function and returns
plain dictionaries. Nothing in this module performs input or output.
"""

import html
import re
from datetime import datetime, time, timedelta

# The MISDA column passes through unchanged. The portal prints a code such as
# SIGNALFAIL or ASCENTSUSPEND and publishes no definition for any of them.

# The bands the flight status report groups its stations under. The heading names the
# pressure the radiosonde reached, so it doubles as the source's own classification of
# how far the ascent got. The final two bands hold ascents that produced no data.
REPORT_SECTIONS = {
    "Above 10 hPa": "ABOVE_10_HPA",
    "Between 20 and 10 hPa": "BETWEEN_20_AND_10_HPA",
    "Between 30 and 20 hPa": "BETWEEN_30_AND_20_HPA",
    "Between 100 and 30 hPa": "BETWEEN_100_AND_30_HPA",
    "Between 200 and 100 hPa": "BETWEEN_200_AND_100_HPA",
    "Less than 200 hPa": "BELOW_200_HPA",
    "MISDA [RS&RW]": "MISDA_RADIOSONDE_AND_RADIOWIND",
    "Radio Wind [RS-Misda]": "MISDA_RADIOWIND",
}

# The thirteen numeric columns of the consumable stock report, in the order the report
# lays them out. The column-group spans in the report header confirm the grouping: five
# instrument types, three balloon types, one unqualified column each for thread,
# batteries and targets, then two chemicals. The instrument and balloon type names belong
# to the report, which never says what they stand for, so this module leaves them as
# they are.
COMMODITY_COLUMNS = (
    "instruments_mk_3",
    "instruments_mk_4",
    "instruments_imdgps",
    "instruments_fgps",
    "instruments_others",
    "balloons_pr875",
    "balloons_chinese",
    "balloons_others",
    "thread",
    "batteries",
    "targets",
    "chemicals_caustic_soda",
    "chemicals_ferro_silicon",
)

# Text the portal repeats on every report. None of it names a station.
PAGE_FURNITURE = {
    "DITUAL",
    "INDIA METEOROLOGICAL DEPARTMENT",
    "UPPER AIR OBSERVATORY MONITORING SYSTEM",
    "UPPER AIR INSTRUMENTS DIVISION(UAL) - MONITORING SYSTEM",
}

# Columns the flight status report measures. A row with none of them recorded no ascent.
MEASURED_COLUMNS = (
    "flight_duration_minutes",
    "radiosonde_maximum_height_pressure_hpa",
    "radiosonde_maximum_height_gpm",
    "radiowind_maximum_height_pressure_hpa",
    "radiowind_maximum_height_km",
    "height_at_100_hpa_gpm",
    "temperature_at_100_hpa_celsius",
)

IST_OFFSET = timedelta(hours=5, minutes=30)

_CELL = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S | re.I)
_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
_SCRIPT = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.S | re.I)
_TAG = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"\s+")


def _rows(markup):
    """Splits report markup into rows of plain cell text.

    Args:
        markup: The text of one portal report.

    Returns:
        A list of rows, each a list of whitespace-collapsed cell strings.
    """
    body = _SCRIPT.sub("", markup)
    return [[_SPACE.sub(" ", html.unescape(_TAG.sub(" ", cell))).strip()
             for cell in _CELL.findall(row)]
            for row in _ROW.findall(body)]


def _number(text):
    """Reads one numeric cell, treating the report's zero as an absent measurement.

    The portal writes 0.0 rather than leaving a cell blank. No height, pressure or
    temperature in this report can legitimately be zero: an ascent that reached zero
    geopotential metres never happened, and the 100 hPa surface never sits at 0 degrees
    Celsius. Reporting those as measurements would misstate the record, so this function
    returns them as absent.

    Args:
        text: The cell's text.

    Returns:
        The value as a float, or None if the cell is blank, unreadable or zero.
    """
    try:
        value = float(text)
    except ValueError:
        return None
    return None if value == 0.0 else value


def _release_time(text):
    """Reads a release time written as four digits of IST clock time.

    Args:
        text: The cell's text, such as `0433`.

    Returns:
        A `datetime.time`, or None if the cell does not hold a valid clock time.
    """
    digits = text.strip()
    if not re.fullmatch(r"\d{3,4}", digits):
        return None
    digits = digits.zfill(4)
    hour, minute = int(digits[:2]), int(digits[2:])
    if hour > 23 or minute > 59:
        return None
    return time(hour, minute)


def _release_utc(day, released):
    """Converts a release clock time in IST to an instant in UTC.

    A station flying the 00 UTC slot releases its balloon the previous evening in UTC,
    and a station flying 12 UTC releases the same morning. Subtracting the fixed IST
    offset from the slot's own date covers both without a special case for either.

    Args:
        day: A `datetime.date` naming the observation date in UTC.
        released: The release clock time in IST as a `datetime.time`.

    Returns:
        A naive `datetime.datetime` in UTC.
    """
    return datetime.combine(day, released) - IST_OFFSET


def parse_flight_status(markup, day, hour):
    """Reads the flight status report for one observation slot.

    Args:
        markup: The text returned by `fetch.flight_status`.
        day: A `datetime.date` naming the observation date in UTC.
        hour: The slot hour in UTC, either 0 or 12.

    Returns:
        A list of dictionaries, one per station that appears in the report.
    """
    records = []
    section = None
    for row in _rows(markup):
        # A band heading stands alone on its own row, except for the first, which the
        # report tucks into the last cell of the column header.
        for cell in row:
            section = REPORT_SECTIONS.get(cell.removesuffix("-Nil-").strip(), section)
        if len(row) != 10 or not row[0] or row[0] == "Station":
            continue

        reason = row[9].strip().upper() or "NONE"
        measurements = dict(zip(MEASURED_COLUMNS, (_number(cell) for cell in row[2:9])))

        # A row with nothing in any measured column records an ascent that never
        # happened, and the portal fills its release column with the slot's own clock
        # time instead of a blank. Those clock times are genuine elsewhere: Patiala
        # released at 17:30 on 2026-09-10 and flew for 105 minutes.
        released = _release_time(row[1])
        if all(value is None for value in measurements.values()):
            released = None

        records.append({
            "observation_date": day,
            "observation_hour_utc": hour,
            "station_name": row[0].strip().upper(),
            "release_time_ist": released.strftime("%H:%M") if released else None,
            "release_time_utc": _release_utc(day, released) if released else None,
            **measurements,
            "misda_reason": reason,
            "ascent_completed": reason == "NONE",
            "report_section": section,
        })
    return _one_row_per_station(records)


def _one_row_per_station(records):
    """Collapses stations the report lists more than once.

    The portal sometimes renders a station's row several times in one report. Most repeats
    carry identical figures and collapse without loss. A few disagree, and this function
    keeps the fullest of them: the row holding the most measurements, and the earliest of
    those when several tie.

    Args:
        records: Records from one report, in the order the report lists them.

    Returns:
        The records with one row per station, still in report order.
    """
    best = {}
    for record in records:
        measured = sum(record[column] is not None for column in MEASURED_COLUMNS)
        name = record["station_name"]
        if name not in best or measured > best[name][0]:
            best[name] = (measured, record)
    return [record for _, record in best.values()]


def parse_ground_status(markup):
    """Reads the ground equipment class recorded against each station.

    The report is a live snapshot of the most recent slot, so this function keys the
    result by station and release time. Matching on both keeps the class off an ascent it
    does not describe.

    Args:
        markup: The text returned by `fetch.ground_status`.

    Returns:
        A dictionary mapping `(station_name, release_time_ist)` to an equipment class.
    """
    classes = {}
    for row in _rows(markup):
        if len(row) != 11 or not row[0] or row[0] == "Station":
            continue
        released = _release_time(row[2])
        if released is None:
            continue
        equipment = row[1].strip().upper()
        if equipment and equipment != "NONE":
            classes[(row[0].strip().upper(), released.strftime("%H:%M"))] = equipment
    return classes


def parse_consumable_stock(markup, day):
    """Reads the consumable stock report for one date.

    A station that files no return at all appears as a single spanning cell rather than a
    row of figures, and this function skips it. That differs from a station which returns
    zero, and which the table records as zero.

    Args:
        markup: The text returned by `fetch.consumable_stock`.
        day: A `datetime.date` naming the report date.

    Returns:
        A list of dictionaries, one per station, holding all thirteen stock columns.
    """
    records = []
    for row in _rows(markup):
        if len(row) != len(COMMODITY_COLUMNS) + 1 or not row[0] or row[0] == "Station":
            continue
        record = {"report_date": day, "station_name": row[0].strip().upper()}
        for column, cell in zip(COMMODITY_COLUMNS, row[1:]):
            try:
                # Keep a zero. It is a real return, not a missing value, and it is why
                # the flight status report shows that station failing every morning.
                record[column] = int(float(cell))
            except ValueError:
                record[column] = None
        records.append(record)
    # The portal repeats a station's row here too, always with identical figures.
    return list({record["station_name"]: record for record in records}.values())


def parse_network_roster(markup):
    """Reads the list of stations in the radiosonde and radiowind network.

    Args:
        markup: The text returned by `fetch.network_roster`.

    Returns:
        A sorted list of station names.
    """
    names = set()
    for row in _rows(markup):
        if len(row) != 1:
            continue
        name = row[0].strip().upper()
        if re.fullmatch(r"[A-Z][A-Z .'&/-]{2,}", name) and name not in PAGE_FURNITURE:
            names.add(name)
    return sorted(names)
