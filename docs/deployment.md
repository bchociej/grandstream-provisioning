# Operating this application

This application follows the adopted [dev-standards repository](standards.md),
including BAS-001 5.0.0, BAS-002 3.0.0, and CAS-001 4.0.0. The README and
that page record each version spec, exact resolution, source ref, and applicability. This file supplies the concrete operating
commands and deployment-specific choices.

## Runtime contract

Target Linux/amd64 for image builds, Compose hosts, and Kubernetes nodes. Compose
sets `platform: linux/amd64`; Kubernetes selects Linux/amd64 nodes. Build directly
from the repository root with
`docker build --platform linux/amd64 -f container/Dockerfile -t grandstream-provisioning:local .`.

One instance serves configuration. Startup reads `/config/devices.toml`, its
referenced templates/secrets, and any selected PEM roots under `/roots/current`.
It validates and renders the entire inventory into `/srv/provision`, then starts
nginx on port 8080. `/healthz` becomes available only after successful rendering.
A render error exits before nginx starts. A failed replacement means an outage
until valid sources are restored; ephemeral output is not a fallback backup.

`/config` and `/roots` are read-only inputs. Generated output is disposable and
contains SIP secrets: Compose uses tmpfs and Kubernetes uses a memory-backed
emptyDir, limited to 64 MiB. Compose container recreation and Kubernetes Pod
replacement discard it, as does host/node loss. An in-Pod container restart can
retain emptyDir contents, but startup still validates and renders before serving. No PVC or shared writer is
needed. Historical generations disappear when the containing tmpfs/Pod volume
is discarded. Back up source snapshots and required root inventories privately, not generated volumes. Do not scale this deployment.

Compose runs one instance; Kubernetes uses one replica and `Recreate`. Expect a
brief outage on updates. Serving does not fetch roots or depend on Internet access
at startup. Run root maintenance explicitly, review selections, and restart to
publish changes. HTTP is private behind a TLS proxy/Ingress or an isolated bootstrap
network; site-specific routing, TLS, and access rules belong in a private overlay.
The Kubernetes base only exposes a ClusterIP Service.

Runtime dependencies are nginx, system Python 3.12 or newer (standard library),
OpenSSL, and OS CA certificates. Serving writes `/srv/provision` and `/tmp`
(nginx PID and temporary request/proxy directories); nginx sends errors to stderr
and access logging is disabled. The image prepares `/run/nginx` at build time.
Root maintenance alone needs write access to `/roots` and outbound verified HTTPS;
it does not run inside the read-only serving mounts. There is no durable database.
Back up the authoritative input/root snapshots outside SCM. The operator terminates
TLS at a private reverse proxy/Ingress and controls subnet/VPN access; this image
serves HTTP on 8080, not public TLS.

## Release verification helper

In a private operator shell, define the following code for comparing rendered
configuration without printing XML, MAC filenames, or credentials. Keep the digest
and image IDs in the private release record, not public CI logs. This digest
identifies effective rendered content, not every unused source file or trust root.

```sh
revision_code='
import hashlib
from pathlib import Path
digest = hashlib.sha256()
for path in sorted(Path("/srv/provision/current").glob("cfg*.xml")):
    digest.update(path.name.encode() + b"\0" + path.read_bytes() + b"\0")
print(digest.hexdigest())
'
```

Run the matching preflight/verification below with a coherent, unchanged input
snapshot. Do not run concurrent source or root updates during these commands.

## Compose

Run commands from the repository root. All paths in the Compose file are resolved
relative to `deploy/compose/`, with explicit paths back to the repository root.
The fixed project name is `grandstream-provisioning`. If migrating from an existing
Compose installation with a different project name, stop that old stack first;
this change does not migrate or delete old named volumes. Keep private backups
before removing any obsolete credential-bearing volumes.

Initial setup:

```sh
cp -r examples config
mkdir -p config/secrets roots
printf '%s\n' 'replace-with-real-password' > config/secrets/1001.txt
chmod -R go-rwx config
# Edit the MAC, SIP server, identities, and secret before starting.
docker compose -f deploy/compose/compose.yaml build
docker compose -f deploy/compose/compose.yaml run --rm --no-deps provisioning render
docker compose -f deploy/compose/compose.yaml up -d --force-recreate --wait
```

No root download is required for the default sample, which selects no roots.
For TLS configurations, fetch the current Mozilla inventory explicitly, using the
same built image. The unprivileged updater keeps host files owned by the operator:

```sh
docker run --rm --platform linux/amd64 --user "$(id -u):$(id -g)" \
  --mount "type=bind,src=$PWD/roots,dst=/roots" \
  grandstream-provisioning:local refresh-roots
```

Before changing a working deployment, record its image ID/digest and save a private
backup snapshot of `config/` and `roots/` outside SCM. Make source edits while no
other operator or scheduled updater is modifying them. Validate and replace:

```sh
docker compose -f deploy/compose/compose.yaml run --rm --no-deps provisioning render
docker compose -f deploy/compose/compose.yaml up -d --force-recreate --wait
docker compose -f deploy/compose/compose.yaml ps
curl --fail --silent http://127.0.0.1:8080/healthz
```

For a release record, use this preflight instead of the plain `render` command;
then recreate and compare the active image and rendered revision:

```sh
expected_image=$(docker image inspect --format '{{.Id}}' grandstream-provisioning:local)
expected_revision=$(docker compose -f deploy/compose/compose.yaml run --rm --no-deps \
  --entrypoint sh provisioning -ec \
  'python3 /app/provision.py render; exec python3 -c "$1"' sh "$revision_code")
docker compose -f deploy/compose/compose.yaml up -d --force-recreate --wait
container_id=$(docker compose -f deploy/compose/compose.yaml ps -q provisioning)
actual_image=$(docker inspect --format '{{.Image}}' "$container_id")
actual_revision=$(docker compose -f deploy/compose/compose.yaml exec -T \
  provisioning python3 -c "$revision_code")
test "$actual_image" = "$expected_image"
test "$actual_revision" = "$expected_revision"
```

For production overrides, use the same `-f` arguments in every command and replace
the local image reference with the intended immutable reference. A failed comparison
means the release is not verified; restore the prior snapshot/image and investigate.

The preflight uses a separate container and temporary output; it cannot change the
running server's generated files. For image changes, build/select the new image
before preflight. The development Compose file uses a local image name; production
private overrides should select an immutable image reference. Recreating is
intentional even when Compose cannot detect changes inside the bind mounts.
Do not use a live `exec ... render` as the normal update path.

Verify one known device's provisioning request and expected non-secret P-values
without logging its credentials, then follow [TLS rollout checks](tls.md) for trust
changes. `/healthz` confirms server startup, not device acceptance or fleet rollout.
Rollback means restoring the old source/root snapshot and image, preflighting it,
and running the same recreate/verify commands. Merely restarting does not undo edits.

For a Compose rollback, the private release archive must contain complete `config/`
and `roots/` directories, and the old image ID must still be present locally. Set
`ROLLBACK_SNAPSHOT` and `ROLLBACK_IMAGE` from that record, then:

```sh
: "${ROLLBACK_SNAPSHOT:?Set the private snapshot directory}"
: "${ROLLBACK_IMAGE:?Set the previous local image ID}"
saved_inputs=$(mktemp -d)
mv config roots "$saved_inputs/"
mkdir config roots
cp -a "$ROLLBACK_SNAPSHOT/config/." config/
cp -a "$ROLLBACK_SNAPSHOT/roots/." roots/
docker tag "$ROLLBACK_IMAGE" grandstream-provisioning:local
docker compose -f deploy/compose/compose.yaml run --rm --no-deps provisioning render
docker compose -f deploy/compose/compose.yaml up -d --force-recreate --wait
```

Repeat the image/rendered-revision and representative-operation checks against the
old release record. Keep the displaced inputs private until recovery is confirmed;
do not print their contents. Production digest overrides must also be reverted.

## Kubernetes

The base is `deploy/kubernetes/`. Select an image available to your cluster and use
a private Kustomize overlay, kept under ignored `config/kubernetes/` or in a
configuration store outside SCM. Separate deployment repositories may track
sanitized manifests, but actual inventory and secrets stay outside SCM. Pin the
image by digest. Do not apply the base's local image placeholder to a production cluster. Configure registry authentication separately
if required. No Kubernetes cluster or live deployment is assumed by this repo.

Kubernetes mounts the inventory/templates/credentials as one generated Secret and
public root PEM files as one generated ConfigMap. The example uses a **flat input
layout** because directory-to-Secret imports do not recursively preserve folders:

```text
config/kubernetes/
  kustomization.yaml
  source/
    devices.toml       # profile template = "ht801.xml"; secret path = "1001.txt"
    ht801.xml
    1001.txt           # actual credential, private
  roots/
    <fingerprint>.pem  # filename must match the selected root's SHA-256
```

Add every referenced file explicitly to the generator. For nested paths, extend the
volume's `items` path mappings in your private overlay. Do not blindly reuse the
Compose example's `templates/` and `secrets/` paths with a flat Secret mount.

Example private `config/kubernetes/kustomization.yaml`:

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: provisioning
resources:
  - ../../deploy/kubernetes
images:
  - name: grandstream-provisioning
    newName: registry.example.net/grandstream-provisioning
    digest: sha256:REPLACE_WITH_YOUR_IMAGE_DIGEST
secretGenerator:
  - name: provisioning-source
    files:
      - source/devices.toml
      - source/ht801.xml
      - source/1001.txt
configMapGenerator:
  - name: provisioning-roots
    files:
      - roots/REPLACE_WITH_SELECTED_FINGERPRINT.pem
```

Use default generator name hashes. Changed source data produces a new Secret or
ConfigMap name in the pod template and therefore a Recreate rollout. Keep previous
objects and private source/image revisions until rollback is no longer needed.
Do not disable suffix hashes or mutate old generated objects in place. Secret
access and encryption at rest are cluster responsibilities. Kubernetes objects
have size limits; this approach is intended for a small inventory and selected
root set, not an unbounded fleet or full backup archive.

Use roots from a freshly refreshed `roots/current` inventory. Copy selected roots
into a fresh overlay `roots/` snapshot; do not carry forward stale files from the
previous one. Render-preflight the intended flat source against the current
inventory and the exact target image before applying:

```sh
# Replace the image variable with the intended registry digest reference.
image='registry.example.net/grandstream-provisioning@sha256:REPLACE_WITH_DIGEST'
docker run --rm --platform linux/amd64 \
  --mount "type=bind,src=$PWD/config/kubernetes/source,dst=/config,readonly" \
  --mount "type=bind,src=$PWD/roots,dst=/roots,readonly" \
  --tmpfs /srv/provision:mode=0755,size=64m \
  "$image" render
```

Ensure the overlay's selected PEM files match that validated current inventory;
then preflight once more against the exact files to be mounted:

```sh
docker run --rm --platform linux/amd64 \
  --mount "type=bind,src=$PWD/config/kubernetes/source,dst=/config,readonly" \
  --mount "type=bind,src=$PWD/config/kubernetes/roots,dst=/roots/current,readonly" \
  --tmpfs /srv/provision:mode=0755,size=64m \
  "$image" render
```

To record the expected rendered revision from the exact Kubernetes input snapshot,
run the same preflight with the verification helper from above:

```sh
expected_revision=$(docker run --rm --platform linux/amd64 \
  --mount "type=bind,src=$PWD/config/kubernetes/source,dst=/config,readonly" \
  --mount "type=bind,src=$PWD/config/kubernetes/roots,dst=/roots/current,readonly" \
  --tmpfs /srv/provision:mode=0755,size=64m --entrypoint sh "$image" -ec \
  'python3 /app/provision.py render; exec python3 -c "$1"' sh "$revision_code")
```

Protect rendered Kustomize output: it includes base64-encoded secrets. Do not print
or commit it. Review your private source diff, then apply:

```sh
kubectl create namespace provisioning --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -k config/kubernetes
kubectl -n provisioning rollout status deployment/grandstream-provisioning --timeout=120s
kubectl -n provisioning get pods -l app=grandstream-provisioning
```

For a deliberate restart of the same snapshot:

```sh
kubectl -n provisioning rollout restart deployment/grandstream-provisioning
kubectl -n provisioning rollout status deployment/grandstream-provisioning --timeout=120s
```

Verify `/healthz` through a private port-forward or your approved TLS route, then
verify an actual device operation as described above. Roll back by restoring the
previous private overlay, image digest, and source/root files and reapplying it;
wait for readiness and verify again. Deployment undo alone is insufficient if
inputs were mutated or old generated objects were deleted. Garbage-collect old
Secret/ConfigMap revisions only after your rollback retention period.

Verify the active revision after rollout, without dumping Secrets or configuration:

```sh
actual_revision=$(kubectl -n provisioning exec deployment/grandstream-provisioning \
  -- python3 -c "$revision_code")
test "$actual_revision" = "$expected_revision"
kubectl -n provisioning get deployment grandstream-provisioning \
  -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'
kubectl -n provisioning get pods -l app=grandstream-provisioning \
  -o jsonpath='{range .items[*]}{.status.containerStatuses[0].imageID}{"\n"}{end}'
```

Compare the configured immutable image and the running image ID with the private
release record. For a multi-platform registry index, record the intended amd64
manifest digest as well; the running platform image ID may differ from the index
digest. Never treat an unexamined mismatch as success.

For Kubernetes rollback, retain a complete private overlay snapshot, including its
image reference and source/root files. Set `ROLLBACK_OVERLAY` to that snapshot;
restore it to the original overlay location so relative base paths stay valid:

```sh
: "${ROLLBACK_OVERLAY:?Set the previous private overlay snapshot}"
saved_overlay=$(mktemp -d)
mv config/kubernetes "$saved_overlay/"
mkdir -p config/kubernetes
cp -a "$ROLLBACK_OVERLAY/." config/kubernetes/
# Repeat the preflight using the restored overlay's image and exact inputs.
kubectl apply -k config/kubernetes
kubectl -n provisioning rollout status deployment/grandstream-provisioning --timeout=120s
```

Repeat the rendered-revision, image, readiness, and representative-operation checks
against that old release. The cluster's Secret RBAC, encryption at rest, private
backup handling, TLS route, and network access policy must be verified by the
operator; manifest rendering alone cannot establish those environment controls.
