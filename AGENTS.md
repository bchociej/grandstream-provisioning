# Repository guidance

This project follows the separately maintained
[dev-standards repository](https://github.com/bchociej/dev-standards).
Before standards work, read its README and docs/adopting.md at the current HEAD
of main for discovery and process. Use a verified current `../dev-standards`
checkout or the canonical GitHub locations; disclose when current main cannot
be accessed. Do not edit the standards repository as part of app work.

Read this repo's README per-standard adoption table and
[docs/standards.md](docs/standards.md) before changing code, CI, image assembly,
or deployment definitions. Each standard has a version spec, exact resolved
version, and source ref. Read the requirements at that specific ref, using
`git -C ../dev-standards show <ref>:<path>` or the recorded canonical links.
Current front matter and new matching versions do not change those resolutions.
Resolve all transitive dependency constraints explicitly.

Follow the current adoption guide and consult the user on a concrete scope before
upgrading standards or remediating gaps unless that scope is already approved.
Preserve existing development norms. Update per-standard records and verification
notes after agreed changes; label incomplete adoption and document exceptions or
lasting limitations. Do not silently upgrade, copy standards here, or replace the
per-standard records with a repository-wide target ref.

Use the locked uv checks documented in README.md. Keep the runtime free of Python
package dependencies and keep image build/publish phases out of Actions unless
explicitly requested. Test Compose and Kustomize changes without deploying to
actual infrastructure. Keep real inventory and credentials outside SCM. Local
commits do not authorize pushes or live deployments.
