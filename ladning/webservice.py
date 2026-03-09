import threading
from typing import List, Callable, Optional

import datetime as dt
from flask import Flask, jsonify, Response, request
import waitress
from flask_cors import CORS

from ladning.logging import log
from ladning.types import Price, ChargingPlan, ChargingRequest, ChargingRequestResponse
from dataclasses import asdict


class LadningService:
    def __init__(self, host: str, port: int, electricity_price_getter: Callable[[], List[Price]],
                 charging_plan_getter: Callable[[], Optional[ChargingPlan]],
                 charging_request_setter: Callable[[ChargingRequest], ChargingRequestResponse]) -> None:
        self._electricity_price_getter = electricity_price_getter
        self._charging_plan_getter = charging_plan_getter
        self._charging_request_setter = charging_request_setter

        # Create Flask application
        self._service = Flask("ladning")

        # Enable cross-site requests
        CORS(self._service)

        # Add API endpoints
        self._service.add_url_rule("/electricity", "electricity", self.electricity, methods=["GET"])
        self._service.add_url_rule("/charging_request", "charging_request", self.charging_request, methods=["POST"])
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
        prices = self._electricity_price_getter()
        charging_plan = self._charging_plan_getter()
        combined = dict(
            charging_plan=None if charging_plan is None else asdict(charging_plan),
            prices=[asdict(p) for p in prices]
        )
        return jsonify(combined)

    def charging_request(self) -> Response:
        # Convert POST data to Python dataclass
        try:
            data = request.json
            if data is None:
                return Response("Request body must be valid JSON", 400)

            # Parse "ready_by" field if applicable
            ready_by = data.get("ready_by")
            if ready_by:
                ready_by = dt.datetime.fromisoformat(ready_by)
                if ready_by.tzinfo is None:
                    return Response("ready_by datetime must have timezone information")

            # Parse "max_average_price_dkk_kwh" field if applicable
            max_average_price_dkk_kwh = float(data["max_average_price_dkk_kwh"]) \
                if "max_average_price_dkk_kwh" in data else None

            # Parse "charge_immediately" field, but default to False if not provided
            charge_immediately: bool = data.get("charge_immediately", False)

            # Parse "battery_target" field if applicable, but default to 100 if not provided
            battery_target = int(data.get("battery_target", 100))
            charging_request = ChargingRequest(battery_target=battery_target,
                                               ready_by=ready_by,
                                               max_average_price_dkk_kwh=max_average_price_dkk_kwh,
                                               charge_immediately=charge_immediately)
        except ValueError as e:
            return Response(f"Unable to parse request parameters: '{e}'", 400)

        # Call setter and return result
        response = self._charging_request_setter(charging_request)
        return jsonify(asdict(response))
