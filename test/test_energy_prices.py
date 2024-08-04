from ladning.energy_prices import get_energy_prices, get_energy_prices_energidataservice


def test_get_energy_prices_get_energy_prices_energidataservice() -> None:
    hourly_prices = get_energy_prices_energidataservice()
    assert len(hourly_prices) > 0
    for hourly_price in hourly_prices:
        assert hourly_price.co2_emission is None

        # Sanity check hours
        # assert hourly_price.start


def test_get_energy_prices_bolius() -> None:
    hourly_prices = get_energy_prices()
    assert len(hourly_prices) > 0
    for hourly_price in hourly_prices:
        assert hourly_price.co2_emission > 0
        assert hourly_price.price_kwh_dkk > 0

        # Sanity check hours
        # assert hourly_price.start
