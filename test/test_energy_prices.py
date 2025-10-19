from ladning.energy_prices import get_energy_prices
import datetime as dt


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
