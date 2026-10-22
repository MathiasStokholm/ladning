from ladning.energy_prices import get_energy_prices
import datetime as dt


def test_get_energy_prices_includes_forecasts(monkeypatch) -> None:
    records = [
        {"date": "2025-01-01T01:00:00Z", "price": 2.0, "forecast": True},
        {"date": "2025-01-01T00:00:00Z", "price": 1.0, "forecast": False},
    ]

    class Response:
        def json(self):
            return {"prices": records}

    def mock_get(url: str) -> Response:
        assert "forecast=true" in url
        return Response()

    monkeypatch.setattr("ladning.energy_prices.requests.get", mock_get)

    prices = get_energy_prices()

    assert [price.forecasted for price in prices] == [False, True]
    assert [price.price_kwh_dkk for price in prices] == [1.0, 2.0]


def test_get_energy_prices() -> None:
    prices = get_energy_prices()
    assert len(prices) > 0
    for price in prices:
        assert price.price_kwh_dkk > 0

    # Check that earliest time is before now and later dates are after now
    dates = [p.start for p in prices]
    assert dates[0] < dt.datetime.now().astimezone()
    for later_date in dates[1:]:
        assert later_date > dt.datetime.now().astimezone()
