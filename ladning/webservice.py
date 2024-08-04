import threading
from typing import List

from flask import Flask, jsonify
import waitress

from ladning.types import HourlyPrice
from dataclasses import asdict


class LadningService:
    def __init__(self, host: str, port: int):
        # Create Flask application
        self._hourly_prices = None
        self._service = Flask("ladning")
        self._service.add_url_rule("/electricity_prices", "electricity_prices", self.electricity_prices)
        self._server = waitress.create_server(self._service, host=host, port=port, threads=1)
        self._server_thread = threading.Thread(target=self._server.run, name="server_thread", daemon=True)
        self._server_thread.start()
        print(f"Started webservice at http://{self._server.effective_host}:{self._server.effective_port}")

    def stop(self) -> None:
        self._server.close()

    def electricity_prices(self):
        if self._hourly_prices is None:
            return "Electricity prices not available yet", 400
        return jsonify([asdict(p) for p in self._hourly_prices])

    def update_electricity_prices(self, hourly_prices: List[HourlyPrice]) -> None:
        self._hourly_prices = hourly_prices
