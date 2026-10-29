import hashlib
import importlib.util
import ssl
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

spec = importlib.util.spec_from_file_location("provision", "app/provision.py")
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


class ProvisionTests(unittest.TestCase):
    def test_escaping_and_missing_credentials(self):
        self.assertEqual(
            p.render("<P34>{{ secret }}</P34>", {"secret": "<&>"}),
            "<P34>&lt;&amp;&gt;</P34>",
        )
        with self.assertRaises(KeyError):
            p.render("{{ missing }}", {})

    def test_path_escape(self):
        with self.assertRaises(ValueError):
            p.contained(Path("/tmp/config"), "../password")

    def test_failed_fleet_preserves_current(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            cfg = base / "config"
            cfg.mkdir()
            (cfg / "template.xml").write_text(
                "<gs_provision><mac>{{ mac }}</mac><config><P34>{{ password }}</P34></config></gs_provision>"
            )
            inventory = '[profiles.test]\nmodel="ht801"\ntemplate="template.xml"\n[devices.000b82010203]\nmodel="ht801"\nprofile="test"\n[devices.000b82010203.values]\npassword="one"\n'
            (cfg / "devices.toml").write_text(inventory)
            output = base / "output"
            p.generate(cfg, base, output)
            original = (output / "current").resolve()
            (cfg / "devices.toml").write_text(
                inventory.replace('password="one"', 'other="two"')
            )
            with self.assertRaises(KeyError):
                p.generate(cfg, base, output)
            self.assertEqual((output / "current").resolve(), original)
            self.assertIn("one", (output / "current/cfg000b82010203.xml").read_text())


class RootBundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.cache = Path(cls.temp.name)
        cls.fingerprints = []
        cls.pems = []
        for index in range(3):
            cert = cls.cache / f"root-{index}.crt"
            subprocess.run(
                [
                    "openssl",
                    "req",
                    "-x509",
                    "-newkey",
                    "rsa:2048",
                    "-nodes",
                    "-keyout",
                    str(cls.cache / f"root-{index}.key"),
                    "-out",
                    str(cert),
                    "-days",
                    "1",
                    "-subj",
                    f"/CN=Fixture {index}",
                    "-addext",
                    "basicConstraints=critical,CA:TRUE",
                ],
                check=True,
                capture_output=True,
            )
            pem = cert.read_text()
            fingerprint = hashlib.sha256(ssl.PEM_cert_to_DER_cert(pem)).hexdigest()
            (cls.cache / (fingerprint + ".pem")).write_text(pem)
            cls.fingerprints.append(fingerprint)
            cls.pems.append(pem)

    def test_bundle_order_and_scalar_compatibility(self):
        self.assertEqual(
            p.load_roots(self.cache, {"a": self.fingerprints})["a"],
            "".join(self.pems),
        )
        self.assertEqual(
            p.load_roots(self.cache, {"b": self.fingerprints[0]})["b"], self.pems[0]
        )

    def test_reject_empty_duplicate_and_invalid_selections(self):
        for roots in (
            {"a": []},
            {"a": ""},
            {"c": self.fingerprints[0]},
            {"a": [self.fingerprints[0], self.fingerprints[0]]},
            {"a": [123]},
        ):
            with self.subTest(roots=roots), self.assertRaises(ValueError):
                p.load_roots(self.cache, roots)

    def test_missing_and_mismatched_inventory_fail(self):
        with tempfile.TemporaryDirectory() as folder:
            cache = Path(folder)
            with self.assertRaises(FileNotFoundError):
                p.load_roots(cache, {"a": self.fingerprints[0]})
            (cache / (self.fingerprints[0] + ".pem")).write_text(self.pems[1])
            with self.assertRaisesRegex(ValueError, "does not match"):
                p.load_roots(cache, {"a": self.fingerprints[0]})

    def test_strict_ht801_template_has_independent_checks_and_bundle(self):
        text = p.render(
            Path("examples/templates/ht801-tls.xml").read_text(),
            {
                "mac": "000b82010203",
                "ca": p.load_roots(self.cache, {"a": self.fingerprints}),
                "provisioning_server": "provision.example.net",
                "sip_server": "sip.example.net",
                "sip_user": "1001",
                "sip_auth": "1001",
                "sip_password": "fixture<&>",
            },
        )
        config = ET.fromstring(text).find("config")
        self.assertEqual(config.findtext("P2386"), "".join(self.pems))
        for parameter in ("P8502", "P8463", "P22030", "P2367", "P2311"):
            self.assertEqual(config.findtext(parameter), "1")
        self.assertEqual(config.findtext("P130"), "2")
        self.assertEqual(config.findtext("P34"), "fixture<&>")


if __name__ == "__main__":
    unittest.main()
