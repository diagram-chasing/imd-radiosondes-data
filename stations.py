"""The station registry for the upper-air network.

The monitoring portal identifies stations by name alone. It publishes no coordinates, no
WMO number and no elevation. Those are resolved here against the station list of NOAA's
Integrated Global Radiosonde Archive, which carries the same stations under its own
spellings.

The registry is therefore the one part of this dataset that is not drawn entirely from
IMD. Every coordinate published in `data/stations.csv` and `data/stations.geojson` comes
from `reference/igra2-station-list.txt`, an unmodified copy of the NOAA file.
"""

import json
from pathlib import Path

import polars as pl

IGRA_LIST = Path("reference/igra2-station-list.txt")

# Fixed-width field positions in the IGRA version 2 station list, as documented in the
# archive's own readme.
IGRA_FIELDS = {
    "igra_id": (0, 11),
    "latitude": (12, 20),
    "longitude": (21, 30),
    "elevation_m": (31, 37),
    "igra_name": (41, 71),
}

# The bounding box of India and its island territories, used to reject a coordinate that
# cannot be right. Maitri, IMD's Antarctic station, falls outside it legitimately and is
# excluded from the test by name.
INDIA_BOUNDS = (5.0, 38.0, 68.0, 98.0)

OUTSIDE_INDIA = {"MAITRI"}

# The archive files Kavali under country code UV and at longitude 0.008. Both are wrong.
# The record is admitted by identifier so that the station's WMO number is still
# published; its coordinate is rejected by the plausibility test below.
MISFILED_ENTRIES = {"UVM00043243"}

# The portal's spellings mapped to the archive's. Where the two agree, no entry is
# needed. Where the archive appends a bracketed identifier or an airport name, prefix
# matching resolves it without an entry here.
STATION_ALIASES = {
    "AHMEDABAD": "AHMADABAD",
    "BANGALORE": "BENGALURU",
    "BHOPAL": "BHOPAL/BAIRAGHAR",
    "BHUBANESWAR": "BHUBANESHWAR",
    "BHUJ": "BHUJ-RUDRAMATA",
    "CHIKALTHANA": "AURANGABAD AIRPORT",
    "CHENNAI": "MADRAS/MINAMBAKKAM",
    "DELHI": "NEW DELHI/SAFDARJUNG",
    "GOA": "GOA/PANJIM",
    "HYDERABAD": "HYDERABAD AIRPORT",
    "IMPHAL": "IMPHAL/TULIHAL",
    "JAIPUR": "JAIPUR / SANGANER",
    "KOCHI": "COCHIN/WILLINGDON",
    "KOLKATA": "KOLKATA/DUM DUM",
    "LUCKNOW": "LUCKNOW/AMAUSI",
    "MACHILIPATNAM": "MACHILIPATNAM/FRANCHPET",
    "MANGALORE": "MANGALORE/PANAMBUR",
    "MOHANBARI": "DIBRUGARH /MOHANBARI",
    "MUMBAI": "BOMBAY / SANTACRUZ",
    "NAGPUR": "NAGPUR SONEGAON",
    "PASSIGHAT": "PASIGHAT",
    "PORTBLAIR": "PORT BLAIR",
    "RAIPUR": "PBO RAIPUR",
    "RAMAGUNDAM": "RAMGUNDAM",
    "RANCHI": "M.O. RANCHI",
    "SRIGANGANAGAR": "GANGANAGAR",
    "VISAKHAPATNAM": "VISHAKHAPATNAM/WALTAIR",
}


def _wmo_id(igra_id):
    """Reads the WMO station number out of an IGRA station identifier.

    An identifier such as `INM00043295` carries the country code, the letter M marking a
    WMO-numbered station, and the number itself in the remaining digits.

    Args:
        igra_id: An IGRA version 2 station identifier.

    Returns:
        The WMO station number as an integer, or None if the identifier does not carry
        one.
    """
    if len(igra_id) != 11 or igra_id[2] != "M":
        return None
    try:
        return int(igra_id[3:])
    except ValueError:
        return None


def read_igra_list(path=IGRA_LIST):
    """Reads the Indian entries of the IGRA version 2 station list.

    Args:
        path: Path to the station list file.

    Returns:
        A list of dictionaries, one per Indian station in the file, including those the
        archive has misfiled under another country.

    Raises:
        FileNotFoundError: If the station list is not present.
    """
    entries = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith("IN") and line[:11] not in MISFILED_ENTRIES:
            continue
        entry = {name: line[start:stop].strip()
                 for name, (start, stop) in IGRA_FIELDS.items()}
        for field in ("latitude", "longitude", "elevation_m"):
            try:
                entry[field] = float(entry[field])
            except ValueError:
                entry[field] = None
        entries.append(entry)
    return entries


def _plausible(name, latitude, longitude):
    """Tests whether a coordinate can belong to the named station.

    The archive carries at least one corrupt Indian record: Kavali is listed at a
    longitude of 0.008, which places it in the Atlantic. A station that fails this test
    is published without coordinates rather than at a false position.

    Args:
        name: The portal's station name.
        latitude: Latitude in decimal degrees, or None.
        longitude: Longitude in decimal degrees, or None.

    Returns:
        True if the coordinate is usable.
    """
    if latitude is None or longitude is None:
        return False
    if name in OUTSIDE_INDIA:
        return True
    south, north, west, east = INDIA_BOUNDS
    return south <= latitude <= north and west <= longitude <= east


def _match(name, entries):
    """Finds the archive entry for one portal station name.

    Matching is by exact name first, then by prefix, because the archive appends airport
    names and bracketed identifiers to some entries. The archive's own end-year field is
    deliberately not consulted: it reads 2010 for Chennai, which launches twice a day.

    Args:
        name: The portal's station name.
        entries: The archive entries returned by `read_igra_list`.

    Returns:
        The matching entry, or None.
    """
    target = STATION_ALIASES.get(name, name)
    exact = [e for e in entries if e["igra_name"] == target]
    if exact:
        return max(exact, key=lambda e: _wmo_id(e["igra_id"]) or 0)
    prefixed = [e for e in entries if e["igra_name"].startswith(target + " ")]
    if len(prefixed) == 1:
        return prefixed[0]
    return None


def build_registry(roster, entries):
    """Builds the station registry from the network roster and the archive.

    Args:
        roster: Station names returned by `parse.parse_network_roster`.
        entries: The archive entries returned by `read_igra_list`.

    Returns:
        A polars DataFrame with one row per station in the roster.
    """
    rows = []
    for name in roster:
        entry = _match(name, entries) or {}
        latitude, longitude = entry.get("latitude"), entry.get("longitude")
        usable = _plausible(name, latitude, longitude)
        rows.append({
            "station_name": name,
            "wmo_id": _wmo_id(entry["igra_id"]) if entry else None,
            "igra_id": entry.get("igra_id"),
            "igra_name": entry.get("igra_name"),
            "latitude": latitude if usable else None,
            "longitude": longitude if usable else None,
            "elevation_m": entry.get("elevation_m") if usable else None,
            "in_network_roster": True,
        })
    return pl.DataFrame(rows, schema={
        "station_name": pl.String,
        "wmo_id": pl.Int64,
        "igra_id": pl.String,
        "igra_name": pl.String,
        "latitude": pl.Float64,
        "longitude": pl.Float64,
        "elevation_m": pl.Float64,
        "in_network_roster": pl.Boolean,
    }).sort("station_name")


def write_stations(registry, root):
    """Writes the station registry as CSV and GeoJSON.

    Stations whose coordinates could not be resolved appear in the CSV with empty
    coordinate columns and are omitted from the GeoJSON, which cannot represent a feature
    without a position.

    Args:
        registry: The DataFrame returned by `build_registry`.
        root: The directory to write into.
    """
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    registry.write_csv(root / "stations.csv")

    features = []
    for row in registry.iter_rows(named=True):
        if row["latitude"] is None or row["longitude"] is None:
            continue
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point",
                         "coordinates": [row["longitude"], row["latitude"]]},
            "properties": {k: v for k, v in row.items()
                           if k not in ("latitude", "longitude")},
        })
    (root / "stations.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, indent=1)
    )
