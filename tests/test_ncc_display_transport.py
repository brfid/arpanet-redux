from __future__ import annotations

import unittest
from socketserver import ThreadingMixIn

from ncc.coexistence_server import CoexistenceDisplayHTTPServer
from ncc.historical_server import HistoricalDisplayHTTPServer
from ncc.journey_server import JourneyDisplayHTTPServer


class PassiveDisplayTransportTests(unittest.TestCase):
    def test_idle_browser_connection_cannot_block_another_request(self) -> None:
        server_types = (
            CoexistenceDisplayHTTPServer,
            HistoricalDisplayHTTPServer,
            JourneyDisplayHTTPServer,
        )

        for server_type in server_types:
            with self.subTest(server_type=server_type.__name__):
                self.assertTrue(issubclass(server_type, ThreadingMixIn))
                self.assertTrue(server_type.daemon_threads)


if __name__ == "__main__":
    unittest.main()
