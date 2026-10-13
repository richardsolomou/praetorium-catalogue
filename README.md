# Praetorium catalogue

This repository owns the upstream source pins, composition, provenance, revocation policy, saved-roster compatibility metadata, retained-build recipes, coverage exceptions and minimal authored corrections in `catalogue/`. KOTC 2 declarations and upstream corrections belong here. Fetched sources, copied rules prose, generated JSON and snapshots stay outside Git. Generated files are published as release assets.

The [application](https://github.com/richardsolomou/praetorium.gg) owns the compiler, generic domain behaviour and migration interpreters. `compiler.json` pins that compiler to a full Git commit. Change the compiler pin when a correction needs new engine support; do not copy its implementation here.

## Authoring and validation

Edit exact source revisions in `catalogue/sources.json`, rules composition in `catalogue/composition.json`, or minimal source-pinned Git patches under `catalogue/patches/`. Preserve correction provenance, released rules identities, retained versions and release history. A stale patch fails materialization.

For local checks, clone the compiler revision from `compiler.json`, run `pnpm install --frozen-lockfile`, and set `CATALOGUE_AUTHORING_DIR` to this checkout's absolute path before running its `pnpm catalogue:check` and `pnpm catalogue:materialize` commands. `CATALOGUE_DIR` must identify an independent output directory, never an activated snapshot symlink. Run the affected source audits and the application’s catalogue preflight before adopting a release.

Pull requests run the pinned compiler's authoring tests, full materialization, source audits, retained correction checks, history preparation, snapshot verification and complete source/runtime projection comparison. Run `node scripts/check.mjs`, `node --test scripts/verify-projections.test.mjs` and `python3 -B -m unittest discover -s scripts` for the publisher's local checks.

Saved-ID replacements and loadout migrations live in `catalogue/retired-ids.json` and `catalogue/roster-migrations.json`. Retained rules signatures and reproduction recipes live in `catalogue/retained-roster-rules.json` and `catalogue/retained-profile-build.json`. Preserve their verified identities and source pins; the application imports this metadata from its pinned authoring checkout without request-time downloads.

Record only a proposed update’s intentional coverage losses in `catalogue/accepted-coverage-losses.json`, with exact entries and reasons. Replace any previous list when preparing a new update. Application CI uses exceptions only when it changes the authoring pin, and still rejects stale entries. Application releases do not modify these files.

## Publishing

Dispatch `catalogue.yml` with `publish` enabled to publish a verified candidate. `activate` defaults to false: publishing a candidate does not advance the R2 discovery pointer. Advance that pointer only after the compatible application is deployed. A publication never changes the files packaged in an existing application image.

GitHub Releases hold `snapshot.zip`, `runtime.zip`, `manifest.json`, `release.json` and `revocations.json`. R2 mirrors the source archive, runtime archive and manifests, and stores a shared pool of gzip-compressed source objects keyed by the SHA256 of their uncompressed content. Snapshot format 4 stores identical content once while retaining every original logical path. Runtime artifacts remain a separate distribution profile from the source/audit snapshot; public offline assets are built and published by the application.

The publisher verifies each GitHub asset and each R2 object after upload; a source object already in R2 must match the local file’s MD5 ETag and size. It refuses mismatched existing artifacts, can resume a matching draft, and publishes discovery only after both mirrors verify. Applications pin exact hashes, download only missing source objects when a local pool exists, and otherwise use a verified source archive. Transport failures may fall back to the GitHub archive; integrity failures stop installation. Installation stages complete output before replacing it and preserves the previous snapshot on failure.

The publisher requires boto3, which the workflow installs, `CATALOGUE_R2_ACCESS_KEY_ID`, `CATALOGUE_R2_SECRET_ACCESS_KEY` and the `CLOUDFLARE_ACCOUNT_ID` repository variable. GitHub’s workflow token publishes release assets; R2 credentials are never stored in Git.

## Withdrawal

Edit `catalogue/revocations.json` to withdraw a snapshot or source, then publish the policy before advancing discovery. Existing application releases also carry their pinned policy; update affected application pins or redeploy when an emergency withdrawal must reach existing images. Revocation blocks installation and retained source loading. Do not delete shared objects blindly: an object can belong to multiple retained snapshots. Remove withdrawn mirrors only after checking their retained references.
