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
    Get the energy prices including tariffs and taxes from Bolius.

    See https://www.bolius.dk/elpriser for more info.

    :return: The hourly energy prices from now until the most recently published price
    """
    endpoint = "https://api.bolius.dk/livedata/v2/type/power"
    price_area = "DK2"  # Price area for Sealand and Copenhagen
    date_start_str = dt.datetime.now().astimezone().strftime("%Y-%m-%dT%H:00")
    date_end_str = next_datetime_at_hour(dt.datetime.now() + dt.timedelta(days=1), hour=23,
                                         minutes=59).astimezone().strftime("%Y-%m-%dT%H:%M")
    url = f"{endpoint}?region={price_area}&co2=1&start={date_start_str}&end={date_end_str}"
    records = requests.get(url).json()["data"]

    def _convert(record: Dict[str, Any]) -> HourlyPrice:
        start = (dt.datetime.strptime(record["date"], "%Y-%m-%d") +
                 dt.timedelta(hours=record["hour"])).astimezone()
        price_kwh_dkk = float(record["price"])
        co2_emission = record["co2"]["average"]
        return HourlyPrice(start=start, price_kwh_dkk=price_kwh_dkk, co2_emission=co2_emission)

    # Sort hourly prices by datetime (first entry is closest to current time)
    hourly_prices = sorted([_convert(r) for r in records], key=lambda p: p.start)
    return hourly_prices
