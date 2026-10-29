"""Strict XML rendering and explicit Mozilla root selection. Python standard library only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import ssl
import subprocess
import tempfile
import tomllib
import urllib.request
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

SOURCE = 'https://curl.se/ca/cacert.pem'
TOKEN = re.compile(r'{{\s*([a-zA-Z_][a-zA-Z0-9_.]*)\s*}}')


def contained(base, name):
    path = (base / name).resolve()
    if not path.is_relative_to(base.resolve()):
        raise ValueError('Path outside input directory')
    return path


def render(template, values):
    def replace(match):
        value = values
        for key in match[1].split('.'):
            value = value[key]
        if not isinstance(value, (str, int, float)):
            raise ValueError('Template values must be scalar')
        return escape(str(value))
    result = TOKEN.sub(replace, template)
    if '{{' in result or '}}' in result:
        raise ValueError('Unsupported template expression')
    return result


def generate(config, cache, output):
    data = tomllib.loads((config / 'devices.toml').read_text())
    rendered = {}
    for raw_mac, device in data['devices'].items():
        mac = raw_mac.lower().replace(':', '').replace('-', '')
        if not re.fullmatch('[0-9a-f]{12}', mac) or mac in rendered:
            raise ValueError('Invalid or duplicate MAC')
        model = device['model'].lower()
        if model not in ('ht801', 'ht814'):
            raise ValueError('Unsupported model')
        profile = data['profiles'][device['profile']]
        if profile['model'].lower() != model:
            raise ValueError('Profile model mismatch')
        values = {**data.get('defaults', {}), **profile.get('values', {}), **device.get('values', {}), 'mac': mac}
        for key, filename in device.get('secrets', {}).items():
            values[key] = contained(config, filename).read_text().rstrip('\r\n')
        roots = device.get('roots', profile.get('roots', {}))
        values['ca'] = {}
        for slot, fingerprint in roots.items():
            fingerprint = fingerprint.lower().replace(':', '')
            if not re.fullmatch('[0-9a-f]{64}', fingerprint):
                raise ValueError('Root fingerprint must be SHA-256')
            cert = contained(cache, fingerprint + '.pem')
            subprocess.run(['openssl', 'verify', '-CAfile', str(cert), str(cert)],
                           check=True, capture_output=True)
            values['ca'][slot] = cert.read_text()
        text = render(contained(config, profile['template']).read_text(), values)
        root = ET.fromstring(text)
        if root.tag != 'gs_provision' or root.findtext('mac') != mac or root.find('config') is None:
            raise ValueError('Invalid Grandstream XML envelope')
        params = [e.tag for e in root.find('config')]
        if any(not re.fullmatch('P[0-9]+', p) for p in params) or len(set(params)) != len(params):
            raise ValueError('Invalid or duplicate P-value')
        rendered[mac] = text
    # Validate the entire fleet before publishing. Atomic directory symlink switch.
    output.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='generation-', dir=output))
    try:
        stage.chmod(0o755)
        for mac, text in rendered.items():
            path = stage / f'cfg{mac}.xml'
            path.write_text(text)
            path.chmod(0o644)
        link = output / '.next'
        link.unlink(missing_ok=True)
        link.symlink_to(stage.name, target_is_directory=True)
        os.replace(link, output / 'current')
    except BaseException:
        shutil.rmtree(stage)
        raise
    # Old generations retained for rollback; they contain secrets. See README.


def refresh(cache):
    with urllib.request.urlopen(SOURCE, timeout=30, context=ssl.create_default_context()) as response:
        if response.url != SOURCE:
            raise ValueError('Unexpected CA download redirect')
        bundle = response.read(2_000_001)
    if len(bundle) > 2_000_000:
        raise ValueError('CA bundle too large')
    certs = re.findall(rb'-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----', bundle, re.S)
    if len(certs) < 50:
        raise ValueError('Unexpected CA bundle')
    cache.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.roots-', dir=cache))
    try:
        for pem in certs:
            fingerprint = hashlib.sha256(ssl.PEM_cert_to_DER_cert(pem.decode())).hexdigest()
            subprocess.run(['openssl', 'x509', '-noout'], input=pem, check=True, capture_output=True)
            (stage / (fingerprint + '.pem')).write_bytes(pem + b'\n')
        (stage / 'manifest.json').write_text(json.dumps({'source': SOURCE, 'sha256': hashlib.sha256(bundle).hexdigest(), 'count': len(certs)}, indent=2))
        # Replace the complete inventory so roots removed upstream cannot be selected.
        link = cache / '.next'
        link.unlink(missing_ok=True)
        link.symlink_to(stage.name, target_is_directory=True)
        os.replace(link, cache / 'current')
    except BaseException:
        shutil.rmtree(stage)
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['render', 'refresh-roots'])
    parser.add_argument('--config', type=Path, default=Path('/config'))
    parser.add_argument('--cache', type=Path, default=Path('/roots'))
    parser.add_argument('--output', type=Path, default=Path('/srv/provision'))
    args = parser.parse_args()
    if args.command == 'refresh-roots':
        refresh(args.cache)
    else:
        generate(args.config, args.cache / 'current', args.output)


if __name__ == '__main__':
    main()
