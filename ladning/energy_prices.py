from typing import List, Dict, Any

from ladning.types import HourlyPrice
import datetime as dt
import requests


def next_datetime_at_hour(current: dt.datetime, hour: int, minutes: int = 0) -> dt.datetime:
    repl = current.replace(hour=hour, minute=minutes, second=0, microsecond=0)
    while repl <= current:
        repl = repl + dt.timedelta(days=1)
    return repl


def get_energy_prices() -> List[HourlyPrice]:
    """
    Get the energy prices including tariffs and taxes from https://elprisen.somjson.dk.

    See https://elprisen.somjson.dk/apidocs/#/Elpriser/get_elpris for more info.

    :return: The hourly energy prices from now until the most recently published price
    """
    radius_elnet_gln_number = "5790000705689"  # Price area for Sealand and Copenhagen
    url = f"https://elprisen.somjson.dk/elpris?GLN_Number={radius_elnet_gln_number}"
    records = requests.get(url).json()["records"]

    def _convert(record: Dict[str, Any]) -> HourlyPrice:
        start = dt.datetime.fromisoformat(record["HourDK"]).astimezone()
        price_kwh_dkk = float(record["Total"])
        return HourlyPrice(start=start, price_kwh_dkk=price_kwh_dkk)

    # Sort hourly prices by datetime (first entry is closest to current time)
    hourly_prices = sorted([_convert(r) for r in records], key=lambda p: p.start)

    # Remove hours prior to current hour
    valid_dt = dt.datetime.now().astimezone() - dt.timedelta(hours=1)
    hourly_prices = [p for p in hourly_prices if p.start >= valid_dt]
    return hourly_prices
