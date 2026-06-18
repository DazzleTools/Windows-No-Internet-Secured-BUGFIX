#!/usr/bin/env python3
"""
Phase 2 IPv6 redirect — reversibility tests (DWP acceptance checks AC-O1/AC-O2).

These prove that the redirect is cleanly undone by the EXISTING reset path
(extended for V6), WITHOUT touching the real registry or hosts file:
  AC-O1 - registry backup -> write V6 -> restore = byte-identical round-trip
  AC-O2 - hosts add V6 entry -> restore = original (IPv4 entry untouched)

The reporter (AC-R4) verifies the same thing on real hardware; this is the
must-pass-before-recruitment gate on our side.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import system_config as sc  # noqa: E402


# --- Fake winreg (in-memory) so no real HKLM access happens --------------------
class _FakeKey:
    def __init__(self, store):
        self.store = store


class _FakeWinreg:
    HKEY_LOCAL_MACHINE = "HKLM"
    KEY_READ = 1
    KEY_WRITE = 2
    REG_SZ = 1

    def __init__(self, initial):
        # store: name -> (value, type)
        self.store = dict(initial)

    def OpenKey(self, root, path, reserved, access):
        return _FakeKey(self.store)

    def CreateKeyEx(self, root, path, reserved, access):
        return _FakeKey(self.store)

    def QueryValueEx(self, key, name):
        if name not in key.store:
            raise FileNotFoundError(name)
        return key.store[name]  # (value, type)

    def SetValueEx(self, key, name, reserved, typ, value):
        key.store[name] = (value, typ)

    def DeleteValue(self, key, name):
        if name not in key.store:
            raise FileNotFoundError(name)
        del key.store[name]

    def CloseKey(self, key):
        pass


class TestRegistryReversibility(unittest.TestCase):
    """AC-O1: backup -> write V6 -> restore is byte-identical."""

    def setUp(self):
        # Windows-default initial state (V4 + V6 values present)
        self.initial = {
            "ActiveWebProbeHost": ("www.msftconnecttest.com", 1),
            "ActiveWebProbePath": ("connecttest.txt", 1),
            "ActiveWebProbeHostV6": ("ipv6.msftconnecttest.com", 1),
            "ActiveWebProbePathV6": ("connecttest.txt", 1),
        }
        self._saved = {
            "winreg": sc.winreg,
            "is_admin": sc.is_admin,
            "subprocess": sc.subprocess,
            "BACKUP_DIR": sc.BACKUP_DIR,
        }
        self.fake = _FakeWinreg(self.initial)
        sc.winreg = self.fake
        sc.is_admin = lambda: True
        # Neutralize the reg.exe export + backup-dir listing
        self._tmp = tempfile.mkdtemp(prefix="ncsi_acO1_")
        sc.BACKUP_DIR = self._tmp

        class _FakeProc:
            returncode = 0
            stderr = b""

        class _FakeSub:
            CalledProcessError = sc.subprocess.CalledProcessError
            SubprocessError = sc.subprocess.SubprocessError
            def run(self, *a, **k):
                return _FakeProc()
        sc.subprocess = _FakeSub()

    def tearDown(self):
        sc.winreg = self._saved["winreg"]
        sc.is_admin = self._saved["is_admin"]
        sc.subprocess = self._saved["subprocess"]
        sc.BACKUP_DIR = self._saved["BACKUP_DIR"]

    def test_round_trip_identical(self):
        snapshot = dict(self.fake.store)

        backup = sc.backup_registry_values()
        self.assertIn(sc.NCSI_REGISTRY_KEY, backup)
        # all four managed values captured
        self.assertEqual(set(backup[sc.NCSI_REGISTRY_KEY]), set(sc.NCSI_MANAGED_VALUES))

        ok = sc.update_ncsi_registry_v6("2001:db8:abcd::1")
        self.assertTrue(ok)
        # the redirect actually changed the V6 host
        self.assertEqual(self.fake.store["ActiveWebProbeHostV6"][0], "2001:db8:abcd::1")
        self.assertNotEqual(self.fake.store, snapshot)

        sc.restore_registry_from_backup(backup)
        # byte-identical to before
        self.assertEqual(self.fake.store, snapshot)

    def test_restore_deletes_values_absent_at_backup(self):
        # If a V6 value did NOT exist before, restore must delete our addition
        del self.fake.store["ActiveWebProbeHostV6"]
        del self.fake.store["ActiveWebProbePathV6"]
        snapshot = dict(self.fake.store)

        backup = sc.backup_registry_values()
        sc.update_ncsi_registry_v6("2001:db8::2")
        self.assertIn("ActiveWebProbeHostV6", self.fake.store)  # added

        sc.restore_registry_from_backup(backup)
        self.assertEqual(self.fake.store, snapshot)  # addition removed


class TestHostsReversibility(unittest.TestCase):
    """AC-O2: add V6 hosts entry -> restore = original; IPv4 entry untouched."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp(prefix="ncsi_acO2_")
        self.hosts = os.path.join(self._tmpdir, "hosts")
        # Pre-existing content: a comment, an unrelated entry, and an existing
        # IPv4 NCSI redirect that must NOT be disturbed by the V6 round-trip.
        self.original = (
            "# hosts file\n"
            "127.0.0.1 localhost\n"
            "10.0.0.5 www.msftconnecttest.com\n"
        )
        with open(self.hosts, "w") as f:
            f.write(self.original)

        self._saved = {
            "HOSTS_FILE_PATH": sc.HOSTS_FILE_PATH,
            "BACKUP_DIR": sc.BACKUP_DIR,
            "is_admin": sc.is_admin,
        }
        sc.HOSTS_FILE_PATH = self.hosts
        sc.BACKUP_DIR = os.path.join(self._tmpdir, "backups")
        sc.is_admin = lambda: True

    def tearDown(self):
        sc.HOSTS_FILE_PATH = self._saved["HOSTS_FILE_PATH"]
        sc.BACKUP_DIR = self._saved["BACKUP_DIR"]
        sc.is_admin = self._saved["is_admin"]

    def _read(self):
        with open(self.hosts) as f:
            return f.read()

    def test_v6_add_then_restore(self):
        ok = sc.update_hosts_file_v6("ipv6.msftconnecttest.com", "2001:db8::1")
        self.assertTrue(ok)
        after_add = self._read()
        self.assertIn("2001:db8::1 ipv6.msftconnecttest.com", after_add)
        # IPv4 NCSI entry still present
        self.assertIn("10.0.0.5 www.msftconnecttest.com", after_add)

        sc.restore_hosts_file()
        after_restore = self._read()
        # our V6 entry is gone
        self.assertNotIn("ipv6.msftconnecttest.com", after_restore)
        # unrelated entry preserved
        self.assertIn("127.0.0.1 localhost", after_restore)

    def test_v6_entry_uses_ipv6_literal_match(self):
        # Idempotency: a second configure updates (not duplicates) the entry
        sc.update_hosts_file_v6("ipv6.msftconnecttest.com", "2001:db8::1")
        sc.update_hosts_file_v6("ipv6.msftconnecttest.com", "2001:db8::99")
        content = self._read()
        self.assertEqual(content.count("ipv6.msftconnecttest.com"), 1)
        self.assertIn("2001:db8::99 ipv6.msftconnecttest.com", content)


if __name__ == "__main__":
    unittest.main(verbosity=2)
