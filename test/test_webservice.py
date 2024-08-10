from typing import List, Optional

import datetime as dt
import requests

from ladning.types import HourlyPrice, ChargingPlan
from ladning.webservice import LadningService


def test_webservice_query() -> None:
    def _mock_hourly_price_getter() -> List[HourlyPrice]:
        return [
            HourlyPrice(dt.datetime.now(), 1.32, 50),
            HourlyPrice(dt.datetime.now() + dt.timedelta(hours=1), 2.5, None),
        ]

    def _mock_charging_plan_getter() -> Optional[ChargingPlan]:
        return ChargingPlan(dt.datetime.now(), dt.datetime.now() + dt.timedelta(hours=1), 90, 100)

    # Port '0' means a random free port
    with LadningService(host="localhost", port=0, electricity_price_getter=_mock_hourly_price_getter,
                        charging_plan_getter=_mock_charging_plan_getter) as service:
        url = f"{service.endpoint}/electricity"
        resp = requests.get(url)
        resp.raise_for_status()
        results = resp.json()
        assert results["charging_plan"] is not None
        assert results["hourly_prices"] is not None
        assert len(results["hourly_prices"]) == 2
