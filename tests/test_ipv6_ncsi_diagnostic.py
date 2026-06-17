#!/usr/bin/env python3
"""
Unit tests for the read-only IPv6 NCSI diagnostic in network_diagnostics.

Covers the IPv6 DWP acceptance checks:
  AC2 - synthetic ULA-only / link-local / GUA inputs classify correctly
  AC3 - the diagnostic path performs no winreg writes (read-only)
  (AC1/AC4 - 'healthy' and 'no-IPv6' classification + never-raises)

The classification core is pure, so it is tested with synthetic inputs and
needs no real network or Windows registry.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "NCSIresolver"))

import network_diagnostics as nd  # noqa: E402


def _addrs(*scopes):
    """Build a synthetic address list from scope names."""
    sample = {
        "global": "2001:db8:1234::1",
        "ula": "fd3e:4f5a:5b81::abcd",
        "link-local": "fe80::1",
        "loopback": "::1",
    }
    return [{"address": sample[s], "scope": s} for s in scopes]


class TestScopeClassification(unittest.TestCase):
    def test_global(self):
        self.assertEqual(nd.classify_ipv6_scope("2001:db8::1"), "global")

    def test_ula(self):
        self.assertEqual(nd.classify_ipv6_scope("fd3e:4f5a:5b81::1"), "ula")

    def test_link_local_with_zone(self):
        self.assertEqual(nd.classify_ipv6_scope("fe80::abcd%11"), "link-local")

    def test_loopback_double_colon_leading(self):
        # Regression: '::1' must not be dropped (anchored regex used to miss it).
        self.assertEqual(nd.classify_ipv6_scope("::1"), "loopback")

    def test_invalid(self):
        self.assertEqual(nd.classify_ipv6_scope("Preferred"), "invalid")
        self.assertEqual(nd.classify_ipv6_scope("infinite"), "invalid")
        self.assertEqual(nd.classify_ipv6_scope("192.168.1.1"), "invalid")


class TestNcsiClassification(unittest.TestCase):
    def _verdict(self, addresses, probe):
        return nd.classify_ipv6_ncsi(addresses, {}, probe)["verdict"]

    def test_no_ipv6(self):
        self.assertEqual(self._verdict([], {"attempted": False}), "NoIPv6")
        # loopback-only is still effectively no usable IPv6
        self.assertEqual(
            self._verdict(_addrs("loopback"), {"attempted": False}), "NoIPv6"
        )

    def test_ula_only_is_no_global_address(self):
        # The reporter's NAT66 case.
        v = nd.classify_ipv6_ncsi(_addrs("ula", "link-local"), {}, {"attempted": True, "success": False})
        self.assertEqual(v["verdict"], "NoGlobalAddress")
        self.assertFalse(v["tool_can_help"])

    def test_link_local_only_is_no_global_address(self):
        v = nd.classify_ipv6_ncsi(_addrs("link-local"), {}, {"attempted": False})
        self.assertEqual(v["verdict"], "NoGlobalAddress")

    def test_global_with_successful_probe_is_healthy(self):
        v = nd.classify_ipv6_ncsi(
            _addrs("global", "link-local"), {},
            {"attempted": True, "success": True, "status": 200, "matched_content": True},
        )
        self.assertEqual(v["verdict"], "Healthy")
        self.assertFalse(v["tool_can_help"])

    def test_global_with_failed_probe_is_probe_blocked(self):
        # The case our tool could potentially help (IPv6 twin of IPv4 problem).
        v = nd.classify_ipv6_ncsi(
            _addrs("global"), {},
            {"attempted": True, "success": False, "status": None},
        )
        self.assertEqual(v["verdict"], "ProbeBlocked")
        self.assertTrue(v["tool_can_help"])

    def test_global_with_unattempted_probe_is_unknown(self):
        v = nd.classify_ipv6_ncsi(_addrs("global"), {}, {"attempted": False})
        self.assertEqual(v["verdict"], "Unknown")


class TestReadOnlyContract(unittest.TestCase):
    def test_registry_read_never_writes(self):
        # AC3: spy on winreg to prove the diagnostic registry path only reads.
        try:
            import winreg
        except ImportError:
            self.skipTest("winreg unavailable (non-Windows)")

        write_calls = []
        originals = {}
        for attr in ("SetValueEx", "CreateKey", "CreateKeyEx", "DeleteValue", "DeleteKey"):
            if hasattr(winreg, attr):
                originals[attr] = getattr(winreg, attr)

                def _spy(*a, _name=attr, **k):
                    write_calls.append(_name)
                    raise AssertionError(f"winreg.{_name} called in read-only path")

                setattr(winreg, attr, _spy)
        try:
            nd.read_ipv6_ncsi_registry()
        finally:
            for attr, fn in originals.items():
                setattr(winreg, attr, fn)

        self.assertEqual(write_calls, [], "registry read path must not write")

    def test_detect_never_raises(self):
        # AC4: orchestrator must return a dict, never raise, even offline.
        state = nd.detect_ipv6_ncsi_state(timeout=1.0)
        self.assertIn("classification", state)
        self.assertIn("verdict", state["classification"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
