# Safe Android release process

1. Build an isolated QA flavor with a higher QA-only `versionCode`.
2. Test business flows and the complete updater cycle on QA. Production manifests remain untouched.
3. Run format, analyzer, all tests, a signed Release build, package/version checks, AOT/debuggable checks, signer verification and SHA-256 verification.
4. Create the GitHub Release and upload the APK asset.
5. Download the asset once and verify its SHA-256 and signer against the local build.
6. Update the matching production manifest **last**. This is the publication switch that makes the notification visible.
7. Verify the raw manifest and APK URLs publicly, then test one field device before broad rollout.

Every real release increments both `versionName` and the monotonically increasing Android `versionCode`. A failed release is corrected by publishing another higher version; never replace an already published APK under the same tag and never downgrade the manifest.

A production-signed APK installed on any field device consumes its
`versionCode`, even if its manifest has not been published yet. If the final
artifact changes after that installation, increment the production
`versionCode` again before publication. Never install an unpublished production
candidate for testing; use the isolated QA flavor. Accounting 1.0.14 and later
also compare the installed APK digest when the version codes are equal, but
that recovery path is a safety net, not a substitute for unique version codes.

`status` must be exactly `published`. Draft or malformed manifests, wrong channels/packages, non-GitHub download hosts, wrong SHA-256 values, older versions and APKs signed by another key are rejected by the applications.

---

# Signed manifests: Workers, Workers Receiver, Fatora

The rules above still apply. These three apps additionally require a detached
Ed25519 signature next to every manifest and a monotonic `sequence`. The
accounting / warehouse / representatives / representatives-delivery manifests
are **not** part of this scheme and are never re-signed or rewritten by it.
Like them, every package has its own manifest file named after its `app` id,
and a manifest names exactly one package.

## Layout and names

| Product | Channel | Package | Manifest (+ `.sig`) | Tag | Asset |
|---|---|---|---|---|---|
| Workers manager | production | `com.example.workers` | `manifests/production/workers.json` | `workers-vX.Y.Z` | `workers-X.Y.Z.apk` |
| Workers receiver | production | `com.example.workers.receiver` | `manifests/production/workers-receiver.json` | `workers-vX.Y.Z` | `workers-receiver-X.Y.Z.apk` |
| Fatora | production | `com.example.fatora` | `manifests/production/fatora.json` | `fatora-vX.Y.Z` | `fatora-X.Y.Z.apk` |
| Workers manager | qa | `com.example.workers.qa` | `manifests/qa/workers.json` | `workers-qa-vX.Y.Z` (prerelease) | `workers-qa-X.Y.Z.apk` |
| Workers receiver | qa | `com.example.workers.receiver.qa` | `manifests/qa/workers-receiver.json` | `workers-qa-vX.Y.Z` (prerelease) | `workers-receiver-qa-X.Y.Z.apk` |
| Fatora | qa | `com.example.fatora.qa` | `manifests/qa/fatora.json` | `fatora-qa-vX.Y.Z` (prerelease) | `fatora-qa-X.Y.Z.apk` |

- One Workers release (`workers-vX.Y.Z`) carries both the manager and the
  receiver APK; each package has its own manifest and signature.
- Manifest root (compiled into the apps):
  `https://raw.githubusercontent.com/ahmedmmo902-byte/family-health-app-releases/main/manifests`
- Immutable download URL:
  `https://github.com/ahmedmmo902-byte/family-health-app-releases/releases/download/<tag>/<asset>`
- The tools derive `apkUrl` as `--base-url` + the local file name, so the
  local APK must already be named exactly like the asset (`workers-1.1.0.apk`,
  `workers-receiver-1.1.0.apk`, `fatora-1.1.0.apk`) and `--base-url` must be
  `https://github.com/ahmedmmo902-byte/family-health-app-releases/releases/download/<tag>/`.
  Optional ABI splits go in the same release as `<asset-stem>-<abi>.apk`.
- Tags and version names are never reused, never moved and never deleted; an
  uploaded asset is never replaced.

## Allowed hosts (proven chain)

Read-only proof on 2026-09-29 (`curl -sI` hop by hop, and `curl -r 0-0` GET)
for four existing assets of this repository (accounting-v1.0.52,
warehouse-v1.0.25, representatives-v1.0.4, representatives-delivery-v1.0.5):

1. `github.com` — `/releases/download/<tag>/<asset>` answers `302 Found`
2. `release-assets.githubusercontent.com` — `/github-production-release-asset/…`
   answers `200` (HEAD) / `206` with `Content-Range` (range GET), `Accept-Ranges: bytes`,
   stable `ETag`, `Content-Type: application/vnd.android.package-archive`.

Manifests: `raw.githubusercontent.com` answers `200` directly (no redirect),
`Cache-Control: max-age=300`, and serves the committed blob byte for byte
(verified by `git hash-object` of the raw bytes == the committed blob for all
five existing manifests at main 1fa2742).

The minimal allowlist is therefore exactly:

```
raw.githubusercontent.com,github.com,release-assets.githubusercontent.com
```

No wildcards; `objects.githubusercontent.com` is **not** used by the current
chain. If GitHub changes the chain, the updater fails closed (no install) and
the allowlist is widened only after a new hop-by-hop proof and a new build.

## Signature files (two formats, do not unify)

The signature always covers the **exact bytes** of the manifest file. Each app
only understands its own tool's format; never copy a signature between apps.

- Workers / Workers receiver — `D:\Workers\workers\tool\update\make_manifest.py sign`
  (or `dart run tool/update/sign_manifest.dart sign`):

  ```json
  {"schema": 1, "alg": "Ed25519", "kid": "uk-workers-prod-2026-10", "sig": "<base64url, no padding>"}
  ```

- Fatora — `D:\advace fatora\fatora\tool\update\make_manifest.py sign`
  (or `dart run tool/update/sign_manifest.dart <manifest> <seed-file> <kid>`):

  ```json
  {"alg": "Ed25519", "kid": "uk-fatora-prod-2026-10", "signature": "<base64url, no padding>"}
  ```

The Python tools write `json.dumps` spacing (shown above); the Dart tools write
the same keys without spaces. Both end with a single `\n` and both parse
identically; only the key names/shape matter, and the bytes of the `.sig` are
not themselves signed. The Python tools accept the PEM PKCS#8 private keys
kept in the secrets store; the Dart tools accept only a base64url 32-byte seed.
Private keys never live in any repository (both tools refuse such paths).

Key ids: production `uk-workers-prod-2026-10` (manager + receiver) and
`uk-fatora-prod-2026-10`; QA `uk-workers-qa-2026-10`, `uk-fatora-qa-2026-10`.
Production builds trust only their product's production key.

## `.gitattributes` and line endings

This clone runs with `core.autocrlf=true`. `.gitattributes` marks
`manifests/**/*.json`, `manifests/**/*.sig` (and the same under `staging/`)
`-text merge=binary`, so Git stores and checks them out byte for byte. Sign the
file only after it sits in its final path under that policy, never edit it
afterwards (not even to reformat), and verify the raw bytes after publication.
`tools/verify_manifest_raw.py` refuses any manifest or signature containing CR.

## `sequence` and `status`

- `sequence` is a positive integer, strictly increasing per (app, channel),
  signed inside the manifest. Devices remember the highest sequence accepted
  and ignore anything lower (replay/rollback protection). Always pass
  `--sequence` explicitly (the Workers tool falls back to Unix time when it is
  omitted, which would make every later explicit small sequence stale). A
  suggested scheme is `YYYYMMDDNN` (e.g. `2026100101`). Never reuse a sequence,
  and never sign a paused candidate with a sequence the later published
  manifest would not exceed.
- `status` is the publication switch: only `published` offers the update.
  Candidates are `paused` (Workers also accepts `withdrawn`). A signed
  non-published manifest with a higher sequence withdraws an offer: devices
  drop the offer and delete its downloads.
- The first bridge release of each product is `required=false`.

## Publication order (after the owner's explicit approval only)

1. Build the final signed APKs; read package/versionCode/versionName with
   `aapt2 dump badging`/`apkanalyzer` and the signer with `apksigner verify
   --print-certs` on the artifacts themselves (never from file names).
2. Create the GitHub Release `<tag>` and upload the assets. Do not touch any
   manifest yet.
3. Re-download every asset from its public immutable URL and verify size,
   SHA-256, signer certificate SHA-256, package and version against the local
   build.
4. Generate each manifest with the product's own `make_manifest.py build`
   (from the same final APK, `--status published`, explicit `--sequence`,
   `--allowed-host` for each proven host, no `--required`), sign it with the
   product's own `make_manifest.py sign`, and run the product's `verify`
   locally (`tools/verify_manifest_raw.py --local-dir …`).
5. Commit the manifest **and** its `.sig` together, last, and push to `main`.
6. After the raw cache expires (≥ 5 minutes, `max-age=300`), re-download the
   raw bytes and verify them:
   `python tools/verify_manifest_raw.py --product <p> --channel production --public-key-file <public.json> --expect-status published --check-asset`.
   A raw verification failure blocks the rollout: withdraw immediately (below).
7. Test one field device before broad rollout.

Never publish a manifest before its asset has been uploaded and publicly
re-verified. Never commit APKs, keystores, PEM/seed files, `key.properties`,
or passwords to this repository.

## Withdrawal / rollback (per product)

Android cannot downgrade, so "rollback" means **stop offering** the release
and ship a fix as a higher version. Never delete a tag or asset, never reuse a
version or sequence.

- **Fatora** — the tool has a dedicated command (no APK needed):

  ```
  python tool/update/make_manifest.py withdraw --manifest fatora.json --sequence <N greater than current> --out fatora.json
  python tool/update/make_manifest.py sign --manifest fatora.json --key <private key outside repos> --kid uk-fatora-prod-2026-10
  python tool/update/make_manifest.py verify --manifest fatora.json --sig fatora.json.sig --public-keys '<prod public key json>'
  ```

  It sets `status=paused` and refuses a sequence not greater than the current one.

- **Workers / Workers receiver** — no `withdraw` subcommand; rebuild the
  manifest from the same published APK (renamed to its asset name) with a
  non-published status and a higher sequence, then sign:

  ```
  python tool/update/make_manifest.py build --app workers --channel production \
      --base-url https://github.com/ahmedmmo902-byte/family-health-app-releases/releases/download/workers-vX.Y.Z/ \
      --allowed-host github.com --universal workers-X.Y.Z.apk --dir <folder> \
      --status withdrawn --sequence <N greater than current> --out workers.json
  python tool/update/make_manifest.py sign --manifest workers.json --key <private key outside repos> --kid uk-workers-prod-2026-10
  ```

  Proven locally with a throwaway key: the output is `status=withdrawn`,
  keeps the package/version/SHA of the APK, and verifies with the Workers
  `verify`. The app treats any signed non-published manifest with a newer
  sequence as a withdrawal. The operator must check the sequence is higher
  (the tool does not compare with the previous manifest) and needs the APK
  file at hand.

After either: commit manifest + `.sig` together, push, wait for the raw cache,
and run `tools/verify_manifest_raw.py … --expect-status paused|withdrawn
--expect-sequence-gt <previous>`. Propagation to devices takes up to the raw
cache time (5 minutes) plus the app's check interval.
