# Staging candidate manifests (Workers, Workers receiver, Fatora)

Candidates are prepared **before** the owner's publish approval. They never go
under `manifests/production/` (or `manifests/qa/`) until the approved
publication step in `RELEASE_PROCESS.md`; only `staging/` is used meanwhile.

```
staging/
├── production/
│   ├── workers.json            + workers.json.sig            (Workers tool, uk-workers-prod-2026-10)
│   ├── workers-receiver.json   + workers-receiver.json.sig   (Workers tool, uk-workers-prod-2026-10)
│   └── fatora.json             + fatora.json.sig             (Fatora tool,  uk-fatora-prod-2026-10)
└── qa/
    └── (same names, QA packages, QA keys uk-*-qa-2026-10)
```

`staging/**/*.json` and `staging/**/*.sig` are `-text` in `.gitattributes`, so
the staged bytes are exactly what gets signed and later copied.

## Steps (coordinator)

1. Take the final signed APKs and copy them into a work folder **outside** this
   repository, renamed to their asset names: `workers-<v>.apk`,
   `workers-receiver-<v>.apk`, `fatora-<v>.apk`. APKs are never committed.
2. Build each manifest with the product's own tool, from that folder:

   ```
   python D:\Workers\workers\tool\update\make_manifest.py build --app workers --channel production ^
     --base-url https://github.com/ahmedmmo902-byte/family-health-app-releases/releases/download/workers-v<v>/ ^
     --allowed-host raw.githubusercontent.com --allowed-host github.com --allowed-host release-assets.githubusercontent.com ^
     --universal workers-<v>.apk --dir <work folder> --status paused --sequence <S> ^
     --notes "<Arabic notes>" --out staging\production\workers.json
   ```

   Same for `--app workers-receiver` (`workers-receiver-<v>.apk`, same tag), and
   for Fatora with `D:\advace fatora\fatora\tool\update\make_manifest.py build
   --app fatora … --base-url …/download/fatora-v<v>/ --universal fatora-<v>.apk`.
   Never pass `--required` for the first bridge release.
3. Candidates stay `--status paused`. Choose `<S>` so the later published
   manifest (built at publication time from the same APK with
   `--status published`) can use a strictly higher sequence; never reuse `<S>`.
4. Sign with the product's own tool and the private key from the secrets store
   (never copied, never inside a repository):

   ```
   python D:\Workers\workers\tool\update\make_manifest.py sign --manifest staging\production\workers.json --key <...\ed25519\update-workers-prod\private.pem> --kid uk-workers-prod-2026-10
   python "D:\advace fatora\fatora\tool\update\make_manifest.py" sign --manifest staging\production\fatora.json --key <...\ed25519\update-fatora-prod\private.pem> --kid uk-fatora-prod-2026-10
   ```

5. Verify the exact staged bytes with the product's own verifier:

   ```
   python tools\verify_manifest_raw.py --product workers --channel production --local-dir staging\production ^
     --public-key-file C:\Users\ahmed\.wf-secrets\ed25519\update-workers-prod\public.json --expect-status paused
   ```

   (`workers-receiver` uses the same Workers key; `fatora` uses
   `update-fatora-prod\public.json`.) Add `--check-asset` only once the assets
   exist publicly.
6. Record in the Production Change Set: tag, asset names, package, versionCode,
   versionName, APK SHA-256 and size (from the manifest), signer SHA-256 (from
   `apksigner`), sequence, status, required, kid.
7. Commit the staged files on the local branch only (no push). At publication
   (after approval), regenerate with `--status published` and a higher
   sequence, sign, verify, and only then place the files under
   `manifests/production/` as the very last step of `RELEASE_PROCESS.md`.

Never place an unsigned or `published` candidate under `manifests/production/`
before the approved publication step.
