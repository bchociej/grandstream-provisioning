import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('provision', 'app/provision.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


class ProvisionTests(unittest.TestCase):
    def test_escaping_and_missing_credentials(self):
        self.assertEqual(p.render('<P34>{{ secret }}</P34>', {'secret': '<&>'}), '<P34>&lt;&amp;&gt;</P34>')
        with self.assertRaises(KeyError):
            p.render('{{ missing }}', {})

    def test_path_escape(self):
        with self.assertRaises(ValueError):
            p.contained(Path('/tmp/config'), '../password')

    def test_failed_fleet_preserves_current(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            cfg = base / 'config'
            cfg.mkdir()
            (cfg / 'template.xml').write_text('<gs_provision><mac>{{ mac }}</mac><config><P34>{{ password }}</P34></config></gs_provision>')
            inventory = '[profiles.test]\nmodel="ht801"\ntemplate="template.xml"\n[devices.000b82010203]\nmodel="ht801"\nprofile="test"\n[devices.000b82010203.values]\npassword="one"\n'
            (cfg / 'devices.toml').write_text(inventory)
            output = base / 'output'
            p.generate(cfg, base, output)
            original = (output / 'current').resolve()
            (cfg / 'devices.toml').write_text(inventory.replace('password="one"', 'other="two"'))
            with self.assertRaises(KeyError):
                p.generate(cfg, base, output)
            self.assertEqual((output / 'current').resolve(), original)
            self.assertIn('one', (output / 'current/cfg000b82010203.xml').read_text())


if __name__ == '__main__':
    unittest.main()
