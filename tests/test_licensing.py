"""Minimal licensing smoke tests."""

from __future__ import annotations

import unittest

from app_licensing import generate_activation_code, machine_request_code


class LicensingTests(unittest.TestCase):
    def test_activation_round_trip(self) -> None:
        request_code = machine_request_code()
        activation_code = generate_activation_code(request_code)
        self.assertTrue(activation_code.startswith("ACT-"))
        self.assertEqual(len(activation_code.replace("-", "")), 23)


if __name__ == "__main__":
    unittest.main()
