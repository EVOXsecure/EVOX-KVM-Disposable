import io
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

from tests.nospawn import NoSpawnMixin
from evoxd import cli
from evoxd.config import Settings
from evoxd.lifecycle import Evox
from evoxd.registry import Registry
from tests.fakehv import FakeHypervisor

MEM = {"MemTotal": 16 * 2**20, "MemAvailable": 12 * 2**20}


class CliTest(NoSpawnMixin, unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = Path(self.tmp.name)
        s = Settings(state_dir=d / "st", runtime_dir=d / "rt", guard_status=d / "none.json")
        self.hv = FakeHypervisor()
        self.hv.add_foreign("TEMPLATE-MAIL")
        self.reg = Registry(s.registry_path)
        self.ev = Evox(s, self.hv, self.reg, net_check=lambda: (False, "guard not running"), meminfo=lambda: MEM)

    def tearDown(self):
        self.reg.close()
        self.tmp.cleanup()

    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = cli.main(list(args), evox_factory=lambda: self.ev)
        return rc, out.getvalue(), err.getvalue()

    def test_flow(self):
        self.assertEqual(self.run_cli("template-import", "TEMPLATE-MAIL")[0], 0)
        self.assertIn("TEMPLATE-MAIL", self.run_cli("template-list")[1])
        rc, out, err = self.run_cli("start", "TEMPLATE-MAIL", "--memory", "3072", "--cpus", "1")
        self.assertEqual(rc, 0)
        self.assertIn("NO network", out)
        self.assertIn("WITHOUT network", err)
        name = out.split()[0]
        self.assertEqual(name, "DISPOSABLE-EMAIL-01")
        lst = self.run_cli("list")[1]
        self.assertIn(name, lst)
        self.assertIn("TEMPLATE-MAIL v1", lst)
        # zuletzt benutzte Werte gelten als Standard
        rc, out, _ = self.run_cli("start", "TEMPLATE-MAIL", "--purpose", "web")
        self.assertIn("DISPOSABLE-WEB-01", out)
        self.assertEqual(self.ev.s.load_last_start()["memory_mib"], 3072)
        self.assertEqual(self.run_cli("stop", "--all")[0], 0)
        self.assertIn("No disposable VMs", self.run_cli("list")[1])

    def test_template_remove_and_verify(self):
        self.run_cli("template-import", "TEMPLATE-MAIL")
        self.run_cli("template-import", "TEMPLATE-MAIL")
        rc, _, err = self.run_cli("template-remove", "TEMPLATE-MAIL")
        self.assertEqual(rc, 1)
        self.assertIn("--version N or --older", err)
        self.assertEqual(self.run_cli("template-verify", "TEMPLATE-MAIL", "--version", "1")[0], 0)
        rc, out, _ = self.run_cli("template-remove", "TEMPLATE-MAIL", "--older")
        self.assertEqual((rc, out), (0, "TEMPLATE-MAIL version 1 removed (TEMPLATE-MAIL-v1.qcow2)\n"))
        self.hv.vol_sha256 = lambda _n: "0" * 64
        rc, out, _ = self.run_cli("template-verify", "TEMPLATE-MAIL")
        self.assertEqual(rc, 3)
        self.assertIn("DAMAGED", out)
        self.assertIn("DAMAGED", self.run_cli("template-list")[1])
        with self.assertRaises(SystemExit):                       # --version und --older schließen sich aus
            self.run_cli("template-remove", "TEMPLATE-MAIL", "--version", "1", "--older")
        self.assertEqual(self.run_cli("template-remove", "TEMPLATE-MAIL", "--version", "2")[0], 0)
        self.assertEqual(self.reg.bases(), [])

    def test_errors_are_messages(self):
        rc, _, err = self.run_cli("start", "TEMPLATE-NONE")
        self.assertEqual(rc, 1)
        self.assertIn("Unknown template", err)
        rc, _, err = self.run_cli("template-import", "VAULT-DEBIAN13")
        self.assertEqual(rc, 1)
        self.assertIn("Invalid template name", err)
        self.assertEqual(self.run_cli("stop")[0], 2)

    def test_netcheck_fails_closed(self):
        rc, out, _ = self.run_cli("netcheck")
        self.assertEqual(rc, 2)
        self.assertIn("NOT OK", out)

    def test_core_limit(self):
        import resource
        self.run_cli("list")
        self.assertEqual(resource.getrlimit(resource.RLIMIT_CORE), (0, 0))


if __name__ == "__main__":
    unittest.main()
