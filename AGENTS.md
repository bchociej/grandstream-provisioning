# Repository guidance

This project follows the separately maintained
[app-standards repository](https://github.com/bchociej/app-standards).
Read [docs/standards.md](docs/standards.md) for its adopted Git revision, index,
applicable standards, and project-specific operating choices before changing code,
CI, image assembly, or deployment definitions. Read the applicable standards at
that revision; a sibling `../standards` checkout can supply them via `git show`.
Use the pinned canonical links if that checkout is unavailable. Do not assume
that the other checkout's working tree matches the adopted revision.

Review the standards index for other applicable guidance when deliberately
adopting a newer revision. Keep references current as part of that adoption;
do not copy the standards here or modify their repository as part of app work.
Document conflicts or justified exceptions in this repository.

Use the locked uv checks documented in README.md. Keep the runtime free of Python
package dependencies and keep image build/publish phases out of Actions unless
explicitly requested. Test Compose and Kustomize changes without deploying to
actual infrastructure. Keep real inventory and credentials outside SCM. Local
commits do not authorize pushes or live deployments.
