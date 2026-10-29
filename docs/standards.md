# Standards applicability and compliance

The canonical collection is [bchociej/app-standards](https://github.com/bchociej/app-standards).
This project adopts revision
[`563e23ec99a8faf2db47d9ccff1e3462558e20a2`](https://github.com/bchociej/app-standards/tree/563e23ec99a8faf2db47d9ccff1e3462558e20a2).
The [complete standards index at that revision](https://github.com/bchociej/app-standards/blob/563e23ec99a8faf2db47d9ccff1e3462558e20a2/README.md)
is the entry point, including for standards added to the collection later.

| Standard | Version | Application here |
| --- | --- | --- |
| [BAS-001: Repository and development fundamentals](https://github.com/bchociej/app-standards/blob/563e23ec99a8faf2db47d9ccff1e3462558e20a2/bas-001-repository-and-development-fundamentals.md) | 1 | Applies to the entire repository, public source, tooling, and CI. |
| [CAS-001: Container application repositories](https://github.com/bchociej/app-standards/blob/563e23ec99a8faf2db47d9ccff1e3462558e20a2/cas-001-container-application-repositories.md) | 1 | Applies to image assembly and Compose/Kubernetes deployment. Inherits BAS-001. |

## Maintaining the reference

Standards are maintained independently. Do not copy or vendor their text, require
a Git submodule for runtime/builds, or change the standards repo during app work.
A sibling checkout named `standards` is convenient but optional. For example,
from this repository root, inspect the adopted index with:

```sh
git -C ../standards show 563e23ec99a8faf2db47d9ccff1e3462558e20a2:README.md
```

When adopting an update, review the collection's index and all relevant standards,
including newly introduced ones; assess applicability instead of assuming every
standard fits this app. Implement required changes or document a justified
exception, verify them, then update this page and the README reference to the same
revision. A newer standards HEAD does not silently change this project's contract.

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

No standards exceptions are currently required. Manifest rendering and local
container tests verify the deployment contract; a live Kubernetes rollout,
site-specific TLS/access policy, and device acceptance still require validation
in the intended environment before deployment. Never push or deploy merely as a
consequence of this standards reference.
