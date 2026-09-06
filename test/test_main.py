import pytest

from main import _charging_state_from_observations


def test_charging_state_from_observations() -> None:
    observations = {"observations": [{"id": 109, "value": 3}]}

    assert _charging_state_from_observations(observations) == "CHARGING"


def test_charging_state_from_observations_requires_operation_mode() -> None:
    with pytest.raises(RuntimeError, match="was not returned"):
        _charging_state_from_observations({"observations": []})


def test_charging_state_from_observations_rejects_unknown_mode() -> None:
    with pytest.raises(RuntimeError, match="Unknown charger operation mode"):
        _charging_state_from_observations({"observations": [{"id": 109, "value": 999}]})
