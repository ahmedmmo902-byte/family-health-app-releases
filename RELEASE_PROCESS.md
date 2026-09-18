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
