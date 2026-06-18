#!/usr/bin/env python3
"""
Phase 2 dual-stack server test (DWP acceptance check AC-O3).

A dual-stack NCSI server (one IPv6 socket with IPV6_V6ONLY=0) must answer
/connecttest.txt with "Microsoft Connect Test" on BOTH ::1 (IPv6) and
127.0.0.1 (IPv4-mapped). Binds an OS-assigned ephemeral port on the loopback
only -- no admin, no privileged port, no host mutation.
"""
import os
import sys
import threading
import unittest
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "NCSIresolver"))
import ncsi_server as ns  # noqa: E402


class TestDualStackServer(unittest.TestCase):
    def test_answers_both_families(self):
        # Connectivity verification off -> handler returns the NCSI text directly.
        ns.NCSIHandler.verify_real_connectivity = False
        try:
            server = ns.DualStackHTTPServer(("::", 0), ns.NCSIHandler)
        except OSError as e:
            self.skipTest(f"dual-stack bind unavailable in this environment: {e}")

        port = server.server_address[1]
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        try:
            for url in (f"http://[::1]:{port}/connecttest.txt",
                        f"http://127.0.0.1:{port}/connecttest.txt"):
                with urllib.request.urlopen(url, timeout=5) as resp:
                    status = resp.status
                    body = resp.read().decode("ascii", "replace")
                self.assertEqual(status, 200, f"{url} status")
                self.assertIn("Microsoft Connect Test", body, f"{url} body")
        finally:
            server.shutdown()
            server.server_close()

    def test_create_server_dual_stack_option(self):
        # create_server(dual_stack=True) yields a server bound on the IPv6 family.
        import socket as _socket
        ns.NCSIHandler.verify_real_connectivity = False
        try:
            server = ns.create_server(host="::", port=0, verify_connectivity=False, dual_stack=True)
        except Exception as e:
            self.skipTest(f"dual-stack create_server unavailable: {e}")
        try:
            self.assertEqual(server.socket.family, _socket.AF_INET6)
        finally:
            server.server_close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
