# swift — Agent Instructions

Part of the RVC ecosystem. **Read [rvc-ecosystem/AGENTS.md](https://github.com/petercorke/rvc-ecosystem/blob/main/AGENTS.md) first** — it defines shared conventions: repo ownership, math invariants, dependency boundaries, git/PR workflow, code standards, tech-debt tracking. This file only adds what's specific to this repo.

| | |
|---|---|
| PyPI package | `swift-sim` |
| Nickname | Swift |
| Owner | Jesse Haviland (`jhavl`) — **not Peter Corke** |
| Default branch | `main` |
| Contribution model | **PR only** |

## Notes specific to this repo

- **This is not Peter's repo.** Collaborator push access exists but must never be used —
  every change goes through a PR, even trivial docs fixes. If your local clone has a `fork`
  remote (Peter's copy) and an `origin` remote (this upstream repo), push branches to `fork`
  and open the PR from there. Never push to `origin`.
- Depends on `spatialgeometry` for scene/shape primitives.
- Default branch is `main` — this repo has already migrated off `master`; don't assume
  otherwise from old references.
