---
name: release-check
description: Procedure for executing pre-release checklist and production readiness audit
---

# Release Check Procedure

## 1. Static Verification
- Run typecheck and linter via `.ai/WORKFLOW.md`.
- Ensure zero errors or warnings.

## 2. Test Suite Completion
- Run full test suite (unit, integration, e2e).
- Confirm 100% pass rate.

## 3. Build & Artifact Verification
- Execute production build command (`npm run build` or equivalent).
- Verify bundle size and absence of build warnings.

## 4. Documentation & State Synchronization
- Confirm `docs/` and `.ai/DECISIONS.md` are up to date.

## 5. Version Bump (Semantic Versioning)
- Determine the bump from the commits since the last tag (`git log $(git describe --tags --abbrev=0)..HEAD --oneline`):
  - **MAJOR**: breaking change (`feat!:`, `fix!:` or a `BREAKING CHANGE:` footer).
  - **MINOR**: new backward-compatible feature (`feat:`).
  - **PATCH**: backward-compatible fix (`fix:`, `perf:`…).
  - **No bump required**: only `docs:`, `chore:`, `refactor:`, `test:`, `style:`, `ci:` or `build:` commits. Release as a **PATCH** only if the operator explicitly requests a release; never use these commit types to justify a MINOR or MAJOR bump.
- Update the `VERSION` file (and the version field of the package manifest, if any).

## 6. Changelog
- Move the `[Unreleased]` entries of `CHANGELOG.md` into a new `[X.Y.Z] - YYYY-MM-DD` section (Keep a Changelog: `Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, `Security`).
- Update the comparison links at the bottom of the file.
- Update `.ai/STATE.md` with the new version.

## 7. Operator Validation, Commit & Tag
- 🚨 Present the version, the changelog entry and the diff to the operator. **Do not commit, tag or push without explicit validation** (`.ai/RULES.md`, rule 7).
- Once validated:
  ```bash
  git switch -c chore/release-vX.Y.Z
  git commit -m "chore(release): vX.Y.Z"
  git push -u origin chore/release-vX.Y.Z
  gh pr create --base main --title "chore(release): vX.Y.Z"
  ```
- After the PR is merged, tag the merge commit on `main`:
  ```bash
  git switch main && git pull
  git tag -a vX.Y.Z -m "vX.Y.Z"
  git push origin vX.Y.Z
  ```

## 8. GitHub Release
- Extract the `[X.Y.Z]` section of `CHANGELOG.md` as release notes and append a full changelog link:
  ```bash
  awk '/^## \[X\.Y\.Z\]/{f=1;next} /^## \[/{f=0} f' CHANGELOG.md > notes.md
  printf '\n**Full Changelog**: https://github.com/<owner>/<repo>/compare/vPREVIOUS...vX.Y.Z\n' >> notes.md
  ```
- Create the release from the existing tag (never let `gh` create the tag):
  ```bash
  gh release create vX.Y.Z --verify-tag --title "vX.Y.Z" --notes-file notes.md --latest
  ```
- Delete the temporary `notes.md` file (it must not be committed).
