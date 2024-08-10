import threading
from typing import List, Callable, Optional

from flask import Flask, jsonify, Response
import waitress

from ladning.logging import log
from ladning.types import HourlyPrice, ChargingPlan
from dataclasses import asdict


class LadningService:
    def __init__(self, host: str, port: int, electricity_price_getter: Callable[[], List[HourlyPrice]],
                 charging_plan_getter: Callable[[], Optional[ChargingPlan]]) -> None:
        self._electricity_price_getter = electricity_price_getter
        self._charging_plan_getter = charging_plan_getter

        # Create Flask application
        self._service = Flask("ladning")
        self._service.add_url_rule("/electricity", "electricity", self.electricity)
        self._server = waitress.create_server(self._service, host=host, port=port, threads=1)
        self._server_thread = threading.Thread(target=self._server.run, name="server_thread", daemon=True)

    @property
    def endpoint(self) -> str:
        return f"http://{self._server.effective_host}:{self._server.effective_port}"

    def start(self) -> None:
        self._server_thread.start()
        log.info(f"Started webservice at {self.endpoint}")

    def stop(self) -> None:
        self._server.close()

    def __enter__(self) -> "LadningService":
        self.start()
        return self

    def __exit__(self, *args) -> None:
        self.stop()

    def electricity(self) -> Response:
        """
        API endpoint to query electricity prices and current charging schedule
        """
        hourly_prices = self._electricity_price_getter()
        charging_plan = self._charging_plan_getter()
        combined = dict(
            charging_plan=None if charging_plan is None else asdict(charging_plan),
            hourly_prices=[asdict(p) for p in hourly_prices]
        )
        return jsonify(combined)
