# Grandstream provisioning

A small Alpine image with nginx, Python's standard library, and OpenSSL. No database,
web admin, application framework, or runtime Python packages. Devices fetch static
`/cfg<lowercase-mac>.xml` files. Unknown devices and generic/model fallback requests
receive 404, so a shared fallback cannot accidentally distribute SIP credentials.

This repo follows **CAS-001 version 1**, standards revision `21b4adc`:
[Container application repositories](../standards/container-applications.md)
(sibling standards checkout; canonical hosted URL not yet configured).
Image files live in `container/`; Compose and Kubernetes definitions live under
`deploy/`. See [deployment operations](docs/deployment.md) for the single-replica
contract, private source layout, preflight, update/restart, and rollback commands.

## Start

```sh
cp -r examples config
mkdir -p config/secrets roots
printf '%s\n' 'replace-with-real-password' > config/secrets/1001.txt
chmod -R go-rwx config
# Change devices.toml MAC, SIP server, user, and password before starting.
docker compose -f deploy/compose/compose.yaml build
docker compose -f deploy/compose/compose.yaml run --rm --no-deps provisioning render
docker compose -f deploy/compose/compose.yaml up -d --force-recreate --wait
```

The default binding is localhost for a TLS reverse proxy. Route a dedicated HTTPS
hostname to port 8080; the proxy must preserve the request path. Alternatively bind
8080 to a specific VPN/LAN address for initial isolated bootstrap. Restrict access
with host/VPN firewall rules to the ATA subnets. MAC addresses are identifiers, not
passwords: any client allowed to reach this service can request another unit's XML.
A shared VPN alone doesn't provide per-device authorization. Use supported device
HTTP authentication and proxy authentication if that separation is needed.

Set each ATA's Config Server Path to the chosen hostname/path, using the appropriate
HTTPS selection for that firmware. Route and resolve that hostname from every VPN
site; no broadcast discovery or same-subnet dependency is involved. Establish correct
NTP time before testing TLS. Keep firmware hosting separate: this image serves no
firmware. Review GDMS, DHCP provisioning overrides, and other management sources so
they do not overwrite these settings. Omitted P-values retain existing device values;
these templates do not reset an ATA to a known baseline.

## Templates and devices

`devices.toml` selects a model and named profile by normalized MAC. Profiles select
an XML file, defaults, and optional root fingerprints. Values merge in order:
global defaults, profile values, device values, then device secret files. Secret
paths are relative to `/config`; only trailing CR/LF is stripped. Keep the whole
config directory private and out of version control. Treat rendered Docker volumes
and backups as credentials too.

Templates support only `{{ name }}` and `{{ nested.name }}`; every substitution is
XML-escaped. Missing values fail the whole render. There are no raw expressions,
conditionals, includes, or executable template code. Use separate profiles for
meaningfully different configurations. Arbitrary model-specific P-values remain
plain XML. HT801's sample config provisions its one SIP account. HT814's starter is
intentionally empty: populate its profiles and four port mappings from the official
configuration template for your exact firmware; the renderer supports independent
values/secrets for every port without imposing a guessed mapping.

After editing, preflight in a separate container, then recreate the serving
instance so startup rendering applies one reviewed snapshot:

```sh
docker compose -f deploy/compose/compose.yaml run --rm --no-deps provisioning render
docker compose -f deploy/compose/compose.yaml up -d --force-recreate --wait
```

Rendering validates all devices and switches one directory symlink atomically.
A preflight failure leaves the running instance untouched. Startup failures stop
the replacement instance; restore the last good source snapshot to recover.
Existing devices fetch changes on their configured provisioning schedule or manual
provision/reboot; this service does not push or reboot them. Generated files live in ephemeral
local memory storage and disappear on instance replacement. Back up source snapshots privately for rollback; do not expose
generated output through another server.

## Root certificates

Use Mozilla's public TLS root inventory, converted and distributed by the curl
project at **https://curl.se/ca/cacert.pem**. The downloader uses system-verified HTTPS,
rejects redirects, bounds download size, parses every certificate with OpenSSL,
and writes a complete new inventory before switching it into place. The manifest
records source, count, and bundle SHA-256. This is HTTPS-authenticated distribution,
not an independently signed bundle. Mozilla browser-specific trust constraints
are not fully represented in PEM; selecting a root does not replicate Firefox's
trust policy.

```sh
# After building the image; this does not restart the serving instance.
docker run --rm --user "$(id -u):$(id -g)" \
  --mount "type=bind,src=$PWD/roots,dst=/roots" \
  grandstream-provisioning:local refresh-roots
```

This refreshes `/roots/current`, **not** device configuration. Identify the root(s)
actually required by your SIP/provisioning providers using their authoritative chain
documentation. Review the SHA-256 fingerprint, then add a profile mapping:

```toml
[profiles.ht801.roots]
a = "64-hex-digit-sha256-fingerprint-without-separators"
# b = "another-reviewed-root-fingerprint"
```

Add explicit XML parameters to the appropriate template:

```xml
<P2386>{{ ca.a }}</P2386>
<!-- <P2486>{{ ca.b }}</P2486> -->
```

A slot accepts one fingerprint or an ordered list of fingerprints, for example
`a = ["<first SHA-256>", "<second SHA-256>", "<third SHA-256>"]`.
The renderer concatenates the selected PEM roots in that order. A three-root
bundle in CA A worked after reboot on tested HT801 firmware 1.0.65.3; larger
bundles, CA B capacity, and HT814 limits remain untested. Do not upload the full
browser bundle. Empty bundles are rejected; omission does not remove stored trust.
The renderer requires selected roots to exist in the **current** upstream inventory;
if Mozilla removes one, the next render fails instead of silently retaining it.
Previously published XML stays available until you review and replace that trust.
Check root validity dates and provider compatibility before promotion. Root refresh
is explicit, with no Internet dependency during service startup or rendering.
If scheduling root maintenance, alert on failure and promote a reviewed inventory
through the same preflight/recreate workflow; do not edit the running instance.
Rebuild the image regularly to update the downloader's own OS trust.
A SHA-256 pin identifies the certificate: when a CA rotates its key/certificate, a
new fingerprint requires review rather than automatic substitution by subject name.

The completed HT801 investigation confirms separate provisioning and SIP
verification controls, shared CA-source selection, and small root bundles after
reboot. It also found no online revocation checks on the tested TLS clients,
unreliable live CA activation and blank-field removal, and unresolved startup
clock behavior. See [TLS deployment and rotation](docs/tls.md) for the client
matrix, GDMS compatibility limits, and staged rollout procedure. HT814 remains
untested. The optional `examples/templates/ht801-tls.xml` provides an explicit
strict HT801 profile; it is not selected by the default example inventory.

## Verification and references

Install OpenSSL (used by certificate checks and tests) and
[uv](https://docs.astral.sh/uv/getting-started/installation/), then sync
the development environment from the committed lockfile:

```sh
uv sync --locked
```

uv creates `.venv` and uses Python 3.12 from `.python-version`, downloading Python
if necessary. No separate pip or virtualenv setup is required. Ruff settings and
the `dev` dependency group live in `pyproject.toml`; `shellcheck-py` supplies the
ShellCheck executable. The project is not packaged or installed, and its runtime
dependency list is empty. The Docker runtime continues to use only Python's
standard library, without uv or the development tools.

Run the same checks as GitHub Actions:

```sh
uv run --locked ruff check .
uv run --locked ruff format --check .
git ls-files -z '*.sh' | xargs -0 -r uv run --locked shellcheck
uv run --locked python -m unittest discover -s tests -v
```

To apply Python import/lint fixes and formatting locally:

```sh
uv run --locked ruff check --fix .
uv run --locked ruff format .
```

Use `uv add --dev <tool>` to add development tools. After intentionally changing
dependency constraints, run `uv lock` and commit both `pyproject.toml` and `uv.lock`.
CI uses `--locked` so inconsistent metadata and lockfiles fail rather than silently
updating the lockfile.

The Checks workflow runs on pushes, pull requests, and manual dispatch using
Python 3.12. It runs tests, Ruff lint/format checks, and ShellCheck for every tracked
`.sh` file. It has no image build or publishing phase.

- [Grandstream XML provisioning guide](https://documentation.grandstream.com/knowledge-base/sip-device-provisioning-guide/)
- [HT812/HT814 administration](https://documentation.grandstream.com/knowledge-base/ht812-ht814-administration-guide/)
- [Mozilla CA extraction and limitations](https://curl.se/docs/caextract.html)

## Keeping deployments private

Only synthetic example identities belong in this repository. Keep actual device
inventories, SIP credentials, and secret files under ignored `config/` and do not
force-add them. Generated configuration, private keys, local environment files,
and local Compose overrides are ignored too. The Docker build context is an
allowlist of application files; deployment data cannot enter it accidentally.
Before publishing changes, inspect `git diff --cached` for secrets and site details.
Git ignore rules do not protect files already tracked or remove historical secrets.
