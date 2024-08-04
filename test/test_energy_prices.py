from ladning.energy_prices import get_energy_prices, get_energy_prices_energidataservice
import datetime as dt


def test_get_energy_prices_get_energy_prices_energidataservice() -> None:
    hourly_prices = get_energy_prices_energidataservice()
    assert len(hourly_prices) > 0
    for hourly_price in hourly_prices:
        assert hourly_price.co2_emission is None

    # Check that earliest time is before now and later dates are after now
    dates = [p.start for p in hourly_prices]
    assert dates[0] < dt.datetime.now().astimezone()
    for later_date in dates[1:]:
        assert later_date > dt.datetime.now().astimezone()


def test_get_energy_prices() -> None:
    hourly_prices = get_energy_prices()
    assert len(hourly_prices) > 0
    for hourly_price in hourly_prices:
        assert hourly_price.co2_emission > 0
        assert hourly_price.price_kwh_dkk > 0

    # Check that earliest time is before now and later dates are after now
    dates = [p.start for p in hourly_prices]
    assert dates[0] < dt.datetime.now().astimezone()
    for later_date in dates[1:]:
        assert later_date > dt.datetime.now().astimezone()
