from typing import List, Dict, Any

from ladning.types import HourlyPrice
import datetime as dt
import requests


def get_energy_prices(supplier_id: str = "radius_c", product_id: str = "vindstoed_danskvind") -> List[HourlyPrice]:
    """
    Get the energy prices including tariffs and taxes from stromligning.dk.

    See https://stromligning.dk/artikler/elpris-api for more info.
    To determine supplier and product IDs, visit https://stromligning.dk/live?netselskab=radius_c&produkt=vindstoed_danskvind&omraade=DK2

    :param supplier_id: String representing the energy supplier, see link above
    :param product_id: String representing the energy product, see link above
    :return: The hourly energy prices from now until the most recently published price
    """
    endpoint = "https://stromligning.dk/api/prices"
    now = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)).isoformat().replace("+00:00", "Z")

    # Setting 'lean' to True means we only get the basic information needed (hour and total price)
    url = f"{endpoint}?from={now}&productId={product_id}&supplierId={supplier_id}&lean=true"
    records = requests.get(url).json()

    def _convert(record: Dict[str, Any]) -> HourlyPrice:
        start = dt.datetime.fromisoformat(record["date"].replace("Z", "+00:00")).astimezone()
        price_kwh_dkk = float(record["price"])
        return HourlyPrice(start=start, price_kwh_dkk=price_kwh_dkk)

    # Sort hourly prices by datetime (first entry is closest to current time)
    hourly_prices = sorted([_convert(r) for r in records], key=lambda p: p.start)

    return hourly_prices
