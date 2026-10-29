# Standards applicability and compliance

Standards source: [bchociej/dev-standards](https://github.com/bchociej/dev-standards).
Start with the **current main** [README](https://github.com/bchociej/dev-standards/blob/main/README.md)
and [adoption guide](https://github.com/bchociej/dev-standards/blob/main/docs/adopting.md)
for discovery and process, disclosing any inability to access current main.
That front matter does not replace this repo's individual adoption records in
[README.md](../README.md#applied-standards).

## Resolved adoption assessment

On October 29, 2026, the standards repo's local main and published main were
verified at `894bf013623224066a3a99ed1d9f14c2b1bd7c67`. The index, adoption guide,
versioning policy, and all three selected standards were read at that commit.
Each row below records its own source ref and resolved commit; their equality is
incidental, not a repository-wide target ref.

| Standard | Version spec | Exact resolution | Source ref / resolved commit | Requirement source |
| --- | --- | --- | --- | --- |
| BAS-001 | `^5.0.0` | 5.0.0 | `894bf013623224066a3a99ed1d9f14c2b1bd7c67` | [BAS-001](https://github.com/bchociej/dev-standards/blob/894bf013623224066a3a99ed1d9f14c2b1bd7c67/bas-001-repository-and-development-fundamentals.md) |
| BAS-002 | `^3.0.0` | 3.0.0 | `894bf013623224066a3a99ed1d9f14c2b1bd7c67` | [BAS-002](https://github.com/bchociej/dev-standards/blob/894bf013623224066a3a99ed1d9f14c2b1bd7c67/bas-002-recording-standards-adoption.md) |
| CAS-001 | `^4.0.0` | 4.0.0 | `894bf013623224066a3a99ed1d9f14c2b1bd7c67` | [CAS-001](https://github.com/bchociej/dev-standards/blob/894bf013623224066a3a99ed1d9f14c2b1bd7c67/cas-001-container-application-repositories.md) |

CAS-001 4.0.0 requires BAS-001 `^5.0.0`; BAS-001 5.0.0 requires BAS-002
`^3.0.0`. These resolutions satisfy the complete dependency set without exceptions.
BAS-001's user/namespace assumptions fit this project; no personalization fork is
needed. CAS-001 applies because this app ships a container for Compose/Kubernetes.

## Legacy migration and maintenance

Previously this repo recorded legacy BAS-001 version 1 and CAS-001 version 1 at
`563e23ec99a8faf2db47d9ccff1e3462558e20a2`, with no BAS-002 adoption.
Those were exact historical identifiers, not shorthand for SemVer. This deliberate
migration assesses the new contracts rather than adding `.0.0` to old versions.
The prior records remain available in this repo's Git history.

The user approved retrying the previously proposed adoption scope once the
dependency conflict was corrected. This migration updates records, agent guidance,
and deployment verification details; it retains the existing Python/uv tools,
dependency-free runtime, single-replica startup rendering, Git workflow, and CI
without builds. Local commits are allowed; no push, publication, or live deployment
is authorized by this adoption.

Standards are maintained independently. A sibling `../dev-standards` checkout is
optional. Read current main front matter first, then retrieve each recorded
requirement separately, for example:

```sh
git -C ../dev-standards show main:README.md
git -C ../dev-standards show main:docs/adopting.md
git -C ../dev-standards show 894bf013623224066a3a99ed1d9f14c2b1bd7c67:bas-001-repository-and-development-fundamentals.md
```

For later upgrades, follow the current adoption guide, review the index for other
applicable standards, propose version specs and exact source resolutions, check
transitive dependencies, and obtain consent for changes beyond approved scope.
Do not silently follow a matching newer release. Update the README records and
these notes after implementation and verification. Disclose incomplete adoption,
exceptions, and limitations; neither references nor version ranges prove compliance.

## Compliance decisions

- **Hosting and privacy:** this application's public SCM is
  [bchociej/grandstream-provisioning](https://github.com/bchociej/grandstream-provisioning).
  Actual MACs, credentials, site inventories, device exports, and private paths
  stay out of SCM. Samples use synthetic identities; model/firmware targets are
  documented. Ignore rules cover local state and secrets; the Docker context is
  an application-file allowlist. Commit author metadata uses a GitHub noreply
  identity. Inspect changes and history before publishing; do not print sensitive
  provisioning responses or rendered Secrets in verification logs.
- **Development and CI:** Python uses uv, pyproject.toml, and uv.lock, with Ruff
  and ShellCheck in the development group. GitHub Actions uses locked installs,
  tests, lint/format checks, read-only repository permissions, and no image build,
  publishing, or deployment phase. Runtime Python package dependencies are empty.
- **Platform and layout:** Linux/amd64 is explicit in Compose and Kubernetes node
  selection and in direct-build instructions. Application source, image files,
  deployment definitions, examples, and operating docs follow CAS-001's layout.
- **Image choice and KISS:** an official Alpine base plus nginx, system Python,
  and OpenSSL supplies the small file server and renderer. A plain nginx image
  alone does not provide the MAC-specific template and reviewed-root selection
  logic; the small stdlib renderer is the deliberate application-specific wrapper.
  There is no framework, database, or configuration controller. Image builds use
  the repository root; no site inputs enter the image. The local image tag is a
  development convenience; production overlays must select an immutable image
  reference and preserve its resolved digest for rollback.
- **Configuration and lifecycle:** this file-serving application benefits from
  CAS-001's optional startup-rendering pattern. Inputs are read-only, generated
  output is ephemeral local storage, rendering precedes readiness, and the final
  server process uses exec. Kubernetes supplies source through a Secret and roots
  through a ConfigMap; Compose uses read-only binds. Those choices do not prescribe
  startup rendering for other applications.
- **Operation and recovery:** one replica, Recreate on Kubernetes, isolated
  preflight, explicit recreation/restart, revisioned source objects, verification,
  and source-plus-image rollback are documented in [deployment.md](deployment.md).
  Root refresh is separate from startup and requires reviewed promotion. TLS
  termination and site-specific access policies belong to the operator's private
  deployment configuration. Actual device trust acceptance has separate checks
  in [tls.md](tls.md); server readiness cannot establish fleet convergence.

No MUST exceptions or SHOULD departures are required. Manifest rendering and local
container tests verify the deployment contract; a live Kubernetes rollout,
site-specific TLS/access policy, and device acceptance still require validation
in the intended environment before deployment. Never push or deploy merely as a
consequence of this standards reference.

## Verification of this adoption

Verified October 29, 2026 against the individual resolutions above:

- README source paths and declared exact versions match the selected standards;
  all local Markdown file links and deployment shell-block syntax passed checks.
- Locked uv synchronization, Ruff lint, Ruff format checking, ShellCheck, and all
  seven unit tests passed using Python 3.12 on Linux/amd64.
- Isolated Compose tests with synthetic credentials verified startup, ephemeral
  output, unchanged active output during preflight, restart activation, failed
  preflight isolation, and matching preflight/active rendered-revision digests.
- Offline Kustomize tests verified overlay paths, image-digest substitution,
  generated source object references, and pod-template changes after source edits.
- Ignore rules and the current diff were reviewed. A targeted privacy/secret
  pattern scan of current tracked files and 51 unique historical blobs found no
  matches; synthetic credentials and fixture identities remain intentionally public.

This assessment changes documentation and adoption guidance, not runtime code,
images, or Actions behavior. No cluster, real ATA, publication, or production
rollback was exercised. Existing deployment-environment limitations above remain;
configured checks and offline tests do not certify a site's live security controls.
