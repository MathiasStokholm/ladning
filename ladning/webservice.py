import threading
from typing import List, Callable

from flask import Flask, jsonify
import waitress

from ladning.logging import log
from ladning.types import HourlyPrice
from dataclasses import asdict


class LadningService:
    def __init__(self, host: str, port: int, electricity_price_getter: Callable[[], List[HourlyPrice]]):
        # Create Flask application
        self._electricity_price_getter = electricity_price_getter
        self._service = Flask("ladning")
        self._service.add_url_rule("/electricity_prices", "electricity_prices", self.electricity_prices)
        self._server = waitress.create_server(self._service, host=host, port=port, threads=1)
        self._server_thread = threading.Thread(target=self._server.run, name="server_thread", daemon=True)
        self._server_thread.start()
        log.info(f"Started webservice at http://{self._server.effective_host}:{self._server.effective_port}")

    def stop(self) -> None:
        self._server.close()

    def electricity_prices(self):
        hourly_prices = self._electricity_price_getter()
        return jsonify([asdict(p) for p in hourly_prices])
