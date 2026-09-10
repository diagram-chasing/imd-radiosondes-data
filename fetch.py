"""HTTP access to the India Meteorological Department upper-air monitoring portal.

IMD's Upper Air Instruments Division operates the portal at https://ddgmui.imd.gov.in/ual.
It requires no authentication, carries no documentation, and IMD's main site does not link
to it. Every function here returns the page markup unchanged; `parse` interprets it.
"""

import time
from datetime import date

import httpx

BASE = "https://ddgmui.imd.gov.in/ual2"

# Observation slots the network files. Every station attempts 00 UTC year round. A
# subset also attempts 12 UTC, and several of those stations fly it only in summer.
SLOTS = (0, 12)

# Earliest date the portal serves. A request for 2008 or earlier returns the report
# scaffolding and no station rows.
ARCHIVE_START = date(2009, 1, 1)

# Delay between requests. A complete backfill sends about 19,000 of them to a small
# departmental server, so this stays in place.
REQUEST_DELAY_SECONDS = 1.5

RETRY_ATTEMPTS = 6

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,*/*",
    "Referer": "https://ddgmui.imd.gov.in/ual",
}


def slot_parameter(day, hour):
    """Formats an observation slot as the portal's `d` query parameter.

    Args:
        day: A `datetime.date` naming the observation date in UTC.
        hour: The slot hour in UTC, either 0 or 12.

    Returns:
        A twelve-character `YYYYMMDDHHMM` string.
    """
    return f"{day:%Y%m%d}{hour:02d}00"


def new_client():
    """Opens an HTTP client configured for the portal.

    The portal presents a certificate that fails to validate against the public trust
    store, so this client skips verification. The connection carries no credentials and
    the portal publishes its reports for unrestricted use, which limits the risk to the
    integrity of a public report.

    Returns:
        An `httpx.Client` that callers are responsible for closing.
    """
    return httpx.Client(timeout=120, headers=HEADERS, verify=False, follow_redirects=True)


def _get(client, path, params=None):
    """Requests one page, retrying with an exponential delay.

    Args:
        client: An open `httpx.Client`.
        path: The page name below `BASE`, such as `DailyFlightStatusReportLive.php`.
        params: An optional mapping of query parameters.

    Returns:
        The response body as text.

    Raises:
        RuntimeError: If every attempt fails.
    """
    for attempt in range(RETRY_ATTEMPTS):
        time.sleep(REQUEST_DELAY_SECONDS)
        try:
            response = client.get(f"{BASE}/{path}", params=params)
            if response.status_code == 200:
                return response.text
        except httpx.HTTPError:
            pass
        time.sleep(min(60, 2 ** attempt))
    raise RuntimeError(f"failed after retries: {path}")


def flight_status(client, day, hour):
    """Retrieves the flight status report for one observation slot.

    This is the report that carries release time, flight duration, the height and pressure
    at which each instrument stopped reporting, and the reason recorded against ascents
    that produced no data.

    Args:
        client: An open `httpx.Client`.
        day: A `datetime.date` naming the observation date in UTC.
        hour: The slot hour in UTC, either 0 or 12.

    Returns:
        The report markup as text.

    Raises:
        RuntimeError: If the request fails after every retry.
    """
    return _get(client, "DailyFlightStatusReportLive.php",
                {"d": slot_parameter(day, hour)})


def consumable_stock(client, day):
    """Retrieves the consumable stock report for one date.

    Args:
        client: An open `httpx.Client`.
        day: A `datetime.date` naming the report date.

    Returns:
        The report markup as text.

    Raises:
        RuntimeError: If the request fails after every retry.
    """
    return _get(client, "DailyStockReportLive.php", {"d": slot_parameter(day, 0)})


def ground_status(client):
    """Retrieves the ground equipment report for the most recent slot.

    This endpoint accepts a `d` parameter but ignores it: a request for a date in 2023
    returns the same content as a request for today. The report is a live snapshot, so
    you cannot backfill it.

    Args:
        client: An open `httpx.Client`.

    Returns:
        The report markup as text.

    Raises:
        RuntimeError: If the request fails after every retry.
    """
    return _get(client, "DailyGndFlightStatusReportLive.php")


def network_roster(client):
    """Retrieves the list of stations in the radiosonde and radiowind network.

    Args:
        client: An open `httpx.Client`.

    Returns:
        The roster markup as text.

    Raises:
        RuntimeError: If the request fails after every retry.
    """
    return _get(client, "rsrwnetwork.php")
