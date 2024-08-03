from typing import List, Dict, Any

from ladning.types import HourlyPrice
import datetime as dt
import requests


def next_datetime_at_hour(current: dt.datetime, hour: int) -> dt.datetime:
    repl = current.replace(hour=hour, minute=0, second=0, microsecond=0)
    while repl <= current:
        repl = repl + dt.timedelta(days=1)
    return repl


def get_energy_prices_energidataservice() -> List[HourlyPrice]:
    price_area = "DK2"  # Price area for Sealand and Copenhagen
    date_str = dt.datetime.now().strftime("%Y-%m-%dT%H:00")
    url = f'https://api.energidataservice.dk/dataset/elspotprices?start={date_str}&filter={{"PriceArea":["{price_area}"]}}'
    records = requests.get(url).json()["records"]

    def _convert(record: Dict[str, Any]) -> HourlyPrice:
        start = dt.datetime.strptime(record["HourDK"], "%Y-%m-%dT%H:%M:%S")
        price_mwh_dkk = record["SpotPriceDKK"]
        price_kwh_dkk = price_mwh_dkk / 1000.0
        return HourlyPrice(start=start, price_kwh_dkk=price_kwh_dkk, co2_emission=None)

    # Sort hourly prices by datetime (first entry is closest to current time)
    hourly_prices = sorted([_convert(r) for r in records], key=lambda p: p.start)
    return hourly_prices


def get_energy_prices() -> List[HourlyPrice]:
    """
    Get the energy prices including tariffs and taxes from Bolius.

    See https://www.bolius.dk/elpriser for more info.

    :return: The hourly energy prices from now until the most recently published price
    """
    endpoint = "https://api.bolius.dk/livedata/v2/type/power"
    price_area = "DK2"  # Price area for Sealand and Copenhagen
    date_start_str = dt.datetime.now().strftime("%Y-%m-%dT%H:00")
    date_end_str = next_datetime_at_hour(dt.datetime.now(), hour=0).strftime("%Y-%m-%dT%H:00")
    url = f"{endpoint}?region={price_area}&co2=1&start={date_start_str}&end={date_end_str}"
    records = requests.get(url).json()["data"]

    def _convert(record: Dict[str, Any]) -> HourlyPrice:
        start = dt.datetime.strptime(record["date"], "%Y-%m-%d") + dt.timedelta(hours=record["hour"])
        price_kwh_dkk = float(record["price"])
        co2_emission = record["co2"]["average"]
        return HourlyPrice(start=start, price_kwh_dkk=price_kwh_dkk, co2_emission=co2_emission)

    # Sort hourly prices by datetime (first entry is closest to current time)
    hourly_prices = sorted([_convert(r) for r in records], key=lambda p: p.start)
    return hourly_prices
