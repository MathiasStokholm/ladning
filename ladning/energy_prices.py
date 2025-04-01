from typing import List, Dict, Any

from ladning.types import HourlyPrice
import datetime as dt
import requests


def get_energy_prices() -> List[HourlyPrice]:
    """
    Get the energy prices including tariffs and taxes from Bolius.

    See https://www.bolius.dk/elpriser for more info.

    :return: The hourly energy prices from now until the most recently published price
    """
    endpoint = "https://nrgi.dk/api/common/pricehistory"
    now = dt.datetime.now().astimezone()

    price_area = "DK2"  # Price area for Sealand and Copenhagen
    # The 'includeGrid' option includes tariffs and taxes in the price
    url = f"{endpoint}?region={price_area}&includeGrid=true"
    url_today = f"{url}&date={now.strftime('%Y-%m-%d')}"
    url_tomorrow = f"{url}&date={(now + dt.timedelta(hours=24)).strftime('%Y-%m-%d')}"

    # Download prices for today and tomorrow
    records = requests.get(url_today).json()["prices"] + requests.get(url_tomorrow).json()["prices"]

    # Exclude predicted prices for now to only use actual prices
    records = [r for r in records if not r["isPrediction"]]

    def _convert(record: Dict[str, Any]) -> HourlyPrice:
        start = dt.datetime.fromisoformat(record["localTime"]).astimezone()
        price_kwh_dkk = float(record["totalPriceInclVat"]) * 0.01  # Convert from øre to DKK
        return HourlyPrice(start=start, price_kwh_dkk=price_kwh_dkk)

    # Sort hourly prices by datetime (first entry is earliest)
    hourly_prices = sorted([_convert(r) for r in records], key=lambda p: p.start)

    # Exclude past times except current hour
    hourly_prices = [p for p in hourly_prices if p.start > (now - dt.timedelta(hours=1))]

    return hourly_prices
