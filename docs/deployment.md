# Operating this application

This application follows **BAS-001 version 1**
([fundamentals](../../standards/bas-001-repository-and-development-fundamentals.md)) and **CAS-001 version 1**
([container application repositories](../../standards/cas-001-container-application-repositories.md)),
standards revision `563e23e`.
The standards checkout is a sibling of this repo; it has no published canonical
URL yet. This file supplies this application's concrete commands and exceptions.

## Runtime contract

One instance serves configuration. Startup reads `/config/devices.toml`, its
referenced templates/secrets, and any selected PEM roots under `/roots/current`.
It validates and renders the entire inventory into `/srv/provision`, then starts
nginx on port 8080. `/healthz` becomes available only after successful rendering.
A render error exits before nginx starts. A failed replacement means an outage
until valid sources are restored; ephemeral output is not a fallback backup.

`/config` and `/roots` are read-only inputs. Generated output is disposable and
contains SIP secrets: Compose uses tmpfs and Kubernetes uses a memory-backed
emptyDir, limited to 64 MiB. Compose container recreation and Kubernetes Pod replacement discard it, as does
host/node loss. An in-Pod container restart can retain emptyDir contents, but
startup still validates and renders before serving. No PVC or shared writer is needed. Historical generations disappear when the containing
tmpfs/Pod volume is discarded. Back up source snapshots and required
root inventories privately, not generated volumes. Do not scale this deployment.

Compose runs one instance; Kubernetes uses one replica and `Recreate`. Expect a
brief outage on updates. Serving does not fetch roots or depend on Internet access
at startup. Run root maintenance explicitly, review selections, and restart to
publish changes. HTTP is private behind a TLS proxy/Ingress or an isolated bootstrap
network; site-specific routing, TLS, and access rules belong in a private overlay.
The Kubernetes base only exposes a ClusterIP Service.

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
docker run --rm --user "$(id -u):$(id -g)" \
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

## Kubernetes

The base is `deploy/kubernetes/`. Select an image available to your cluster and use
a private Kustomize overlay, kept under ignored `config/kubernetes/` or in a
configuration store outside SCM. Separate deployment repositories may track
sanitized manifests, but actual inventory and secrets stay outside SCM. Pin the image by digest. Do not apply the base's local image
placeholder to a production cluster. Configure registry authentication separately
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
docker run --rm \
  --mount "type=bind,src=$PWD/config/kubernetes/source,dst=/config,readonly" \
  --mount "type=bind,src=$PWD/roots,dst=/roots,readonly" \
  --tmpfs /srv/provision:mode=0755,size=64m \
  "$image" render
```

Ensure the overlay's selected PEM files match that validated current inventory;
then preflight once more against the exact files to be mounted:

```sh
docker run --rm \
  --mount "type=bind,src=$PWD/config/kubernetes/source,dst=/config,readonly" \
  --mount "type=bind,src=$PWD/config/kubernetes/roots,dst=/roots/current,readonly" \
  --tmpfs /srv/provision:mode=0755,size=64m \
  "$image" render
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
