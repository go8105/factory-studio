"""Reject backwards or incoherent clocks before creating a disposable CI DB."""

import unittest
from datetime import UTC, datetime, timedelta

from gw_integration_check import clock_preflight


class ClockPreflightTest(unittest.TestCase):
    def observe(self, database, hosts):
        class Connection:
            def scalar(self, _statement):
                return next(database)

        return clock_preflight(
            Connection(),
            samples=3,
            delay=0,
            host_clock=lambda: next(hosts),
            pause=lambda _delay: None,
        )

    def clocks(self):
        start = datetime(2026, 11, 5, tzinfo=UTC)
        database = [start + timedelta(seconds=n, milliseconds=5) for n in range(3)]
        hosts = [
            start + timedelta(seconds=n, milliseconds=m)
            for n in range(3)
            for m in (0, 10)
        ]
        return database, hosts

    def test_coherent_clock_sample_is_not_continuous_certification(self):
        database, hosts = self.clocks()
        result = self.observe(iter(database), iter(hosts))
        self.assertTrue(result["stableSample"])
        self.assertFalse(result["continuousStabilityVerified"])
        self.assertFalse(result["signedEvidence"])

    def test_database_backwards_is_refused_even_with_small_host_difference(self):
        database, hosts = self.clocks()
        database[1] = database[0] - timedelta(milliseconds=1)
        result = self.observe(iter(database), iter(hosts))
        self.assertFalse(result["stableSample"])
        self.assertEqual(result["databaseBackwardsCount"], 1)

    def test_host_backwards_is_refused(self):
        database, hosts = self.clocks()
        hosts[3] = hosts[2] - timedelta(milliseconds=1)
        result = self.observe(iter(database), iter(hosts))
        self.assertFalse(result["stableSample"])
        self.assertEqual(result["hostBackwardsCount"], 1)

    def test_query_latency_is_not_misclassified_as_clock_skew(self):
        database, hosts = self.clocks()
        hosts[1] = hosts[0] + timedelta(milliseconds=800)
        result = self.observe(iter(database), iter(hosts))
        self.assertTrue(result["stableSample"])
        self.assertEqual(result["maxOutsideHostWindowMs"], 0)

    def test_database_outside_host_window_is_refused(self):
        database, hosts = self.clocks()
        database = [x + timedelta(seconds=2) for x in database]
        result = self.observe(iter(database), iter(hosts))
        self.assertFalse(result["stableSample"])
        self.assertGreater(result["maxOutsideHostWindowMs"], 250)


if __name__ == "__main__":
    unittest.main()
