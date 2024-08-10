import json
from typing import List, Optional, Callable

import datetime as dt

import pytest
import requests

from ladning.types import HourlyPrice, ChargingPlan, ChargingRequest, ChargingRequestResponse
from ladning.webservice import LadningService

# Use any free port for web services
FREE_PORT = 0
HOST_ADDRESS = "127.0.0.1"  # This has to be an IPv4 address for webservice to not break


@pytest.fixture
def hourly_price_getter() -> Callable[[], List[HourlyPrice]]:
    def _func():
        return [
            HourlyPrice(dt.datetime.now(), 1.32, 50),
            HourlyPrice(dt.datetime.now() + dt.timedelta(hours=1), 2.5, None),
        ]

    return _func


@pytest.fixture
def charging_plan_getter() -> Callable[[], Optional[ChargingPlan]]:
    return lambda: ChargingPlan(dt.datetime.now(), dt.datetime.now() + dt.timedelta(hours=1), 90, 100)


@pytest.fixture()
def charging_request_setter() -> Callable[[ChargingRequest], ChargingRequestResponse]:
    return lambda _: ChargingRequestResponse(success=True, reason="")


def test_webservice_query(hourly_price_getter: Callable[[], List[HourlyPrice]],
                          charging_plan_getter: Callable[[], Optional[ChargingPlan]],
                          charging_request_setter: Callable[[ChargingRequest], ChargingRequestResponse]) -> None:
    """
    Test that the "/electricity" API endpoint can be queried with HTTP GET and that it returns a charging plan and
    hourly pries
    """
    with LadningService(host=HOST_ADDRESS, port=FREE_PORT, electricity_price_getter=hourly_price_getter,
                        charging_plan_getter=charging_plan_getter,
                        charging_request_setter=charging_request_setter) as service:
        url = f"{service.endpoint}/electricity"
        resp = requests.get(url)
        resp.raise_for_status()
        results = resp.json()
        assert results["charging_plan"] is not None
        assert results["hourly_prices"] is not None
        assert len(results["hourly_prices"]) == 2


def test_webservice_charging_request(hourly_price_getter: Callable[[], List[HourlyPrice]],
                                     charging_plan_getter: Callable[[], Optional[ChargingPlan]]) -> None:
    """
    Test that the "/charging_request" API endpoint can be called with HTTP POST and that it returns the result of the
    charging request
    """

    def success(_: ChargingRequest) -> ChargingRequestResponse:
        return ChargingRequestResponse(success=True, reason="")

    def failure(_: ChargingRequest) -> ChargingRequestResponse:
        return ChargingRequestResponse(success=False, reason="It failed!")

    request_data = dict(battery_target=100, ready_by=(dt.datetime.now() + dt.timedelta(hours=5)).isoformat())
    headers = {'Content-type': 'application/json'}

    # Test success
    with LadningService(host=HOST_ADDRESS, port=FREE_PORT, electricity_price_getter=hourly_price_getter,
                        charging_plan_getter=charging_plan_getter, charging_request_setter=success) as service:
        url = f"{service.endpoint}/charging_request"
        resp = requests.post(url, json=request_data, headers=headers)
        resp.raise_for_status()
        results = resp.json()
        assert results["success"] is True
        assert results["reason"] == ""

    # Test failure
    with LadningService(host=HOST_ADDRESS, port=FREE_PORT, electricity_price_getter=hourly_price_getter,
                        charging_plan_getter=charging_plan_getter, charging_request_setter=failure) as service:
        url = f"{service.endpoint}/charging_request"
        resp = requests.post(url, json=request_data, headers=headers)
        resp.raise_for_status()
        results = resp.json()
        assert results["success"] is False
        assert results["reason"] == "It failed!"
