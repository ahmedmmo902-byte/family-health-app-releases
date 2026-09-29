"""Verify a Workers / Workers-receiver / Fatora manifest + detached .sig on the
EXACT bytes a device would read, using each app's OWN `make_manifest.py verify`.

Release-machine tool; it needs no private key and never writes to the network.

Remote (the published raw bytes, after a push):

    python tools/verify_manifest_raw.py --product workers --channel production \
        --public-key-file C:/Users/ahmed/.wf-secrets/ed25519/update-workers-prod/public.json

Local (a candidate before publication, e.g. under staging/):

    python tools/verify_manifest_raw.py --product fatora --channel production \
        --local-dir staging/production \
        --public-key-file C:/Users/ahmed/.wf-secrets/ed25519/update-fatora-prod/public.json

Options:
    --root URL           manifest root (default: the production raw root below);
                         the files read are <root>/<channel>/<product>.json[.sig]
    --local-dir DIR      read <DIR>/<product>.json[.sig] instead of downloading
    --public-keys JSON   '[{"kid":"..","public_key":"<b64url raw 32 bytes>"}]'
    --public-key-file F  a public.json ({kid, public_key}) or a list of them
    --expect-status S    fail unless manifest.status == S (e.g. published)
    --expect-sequence-gt N  fail unless manifest.sequence > N
    --check-asset        HEAD the apkUrl (following redirects hop by hop) and
                         fail if a hop leaves the allowlist or the final
                         Content-Length differs from sizeBytes
    --workers-repo DIR / --fatora-repo DIR   where the app tools live

Checks, in order (any failure -> exit 1):
  1. bytes are read as bytes (no text decoding / newline translation) and
     contain no CR (0x0D) -- the repo stores manifests with `-text`;
  2. the .sig has the shape the product's own tool writes:
       Workers / Workers-receiver: {"schema":1,"alg":"Ed25519","kid":..,"sig":..}
       Fatora:                     {"alg":"Ed25519","kid":..,"signature":..}
  3. manifest app/channel/packageName match the product and channel, every
     download URL is https on an allowlisted host, `sequence` is a positive int;
  4. the product's `make_manifest.py verify` accepts the exact bytes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from urllib.parse import urlparse

DEFAULT_ROOT = ("https://raw.githubusercontent.com/ahmedmmo902-byte/"
                "family-health-app-releases/main/manifests")
# Proven by read-only curl of the real chain (see RELEASE_PROCESS.md):
# manifest -> raw.githubusercontent.com; asset -> github.com 302 ->
# release-assets.githubusercontent.com 200/206. No wildcards.
ALLOWED_HOSTS = {"raw.githubusercontent.com", "github.com",
                 "release-assets.githubusercontent.com"}

PRODUCTS = {
    "workers": {"tool": "workers", "packages": {
        "production": "com.example.workers", "qa": "com.example.workers.qa"}},
    "workers-receiver": {"tool": "workers", "packages": {
        "production": "com.example.workers.receiver",
        "qa": "com.example.workers.receiver.qa"}},
    "fatora": {"tool": "fatora", "packages": {
        "production": "com.example.fatora", "qa": "com.example.fatora.qa"}},
}
DEFAULT_REPOS = {"workers": r"D:\Workers\workers",
                 "fatora": r"D:\advace fatora\fatora"}


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    sys.exit(1)


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={
        "User-Agent": "family-health-release-verify/1",
        "Cache-Control": "no-cache",
        "Accept-Encoding": "identity"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            if response.status != 200:
                fail(f"{url}: HTTP {response.status}")
            final = urlparse(response.geturl()).hostname or ""
            if final not in ALLOWED_HOSTS:
                fail(f"{url}: served from non-allowlisted host {final}")
            data = response.read()
            print(f"fetched {url} ({len(data)} bytes, ETag "
                  f"{response.headers.get('ETag')}, X-Cache "
                  f"{response.headers.get('X-Cache')})")
            return data
    except urllib.error.HTTPError as error:
        fail(f"{url}: HTTP {error.code}")
    except urllib.error.URLError as error:
        fail(f"{url}: {error.reason}")
    return b""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # noqa: D401
        return None


def check_asset(url: str, size: int) -> None:
    opener = urllib.request.build_opener(_NoRedirect)
    for hop in range(1, 6):
        parsed = urlparse(url)
        host = parsed.hostname or ""
        if parsed.scheme != "https" or host not in ALLOWED_HOSTS:
            fail(f"asset hop {hop}: {parsed.scheme}://{host} is not allowlisted")
        request = urllib.request.Request(url, method="HEAD", headers={
            "User-Agent": "family-health-release-verify/1"})
        try:
            response = opener.open(request, timeout=60)
            status, headers = response.status, response.headers
        except urllib.error.HTTPError as error:
            status, headers = error.code, error.headers
        print(f"asset hop {hop}: {host} -> HTTP {status}")
        if status in (301, 302, 303, 307, 308):
            url = headers.get("Location", "")
            continue
        if status != 200:
            fail(f"asset HEAD ended with HTTP {status}")
        length = headers.get("Content-Length")
        if length is None or int(length) != size:
            fail(f"asset Content-Length {length} != manifest sizeBytes {size}")
        print(f"asset size OK ({size} bytes)")
        return
    fail("too many redirects for the asset")


def load_keys(args: argparse.Namespace) -> str:
    if args.public_keys:
        value = json.loads(args.public_keys)
    elif args.public_key_file:
        with open(args.public_key_file, "rb") as handle:
            value = json.loads(handle.read().decode("utf-8-sig"))
    else:
        fail("pass --public-keys or --public-key-file")
        return ""
    if isinstance(value, dict):
        value = [value]
    entries = [{"kid": e["kid"], "public_key": e["public_key"]} for e in value]
    if not entries:
        fail("no public keys")
    return json.dumps(entries)


def check_sig_shape(product: str, sig: dict) -> None:
    if PRODUCTS[product]["tool"] == "workers":
        expected = {"schema", "alg", "kid", "sig"}
        if set(sig) != expected or sig.get("schema") != 1:
            fail(f"Workers .sig must be exactly {sorted(expected)} with schema 1; "
                 f"got {sorted(sig)}")
    else:
        expected = {"alg", "kid", "signature"}
        if set(sig) != expected:
            fail(f"Fatora .sig must be exactly {sorted(expected)}; got {sorted(sig)}")
    if sig.get("alg") != "Ed25519" or not str(sig.get("kid", "")).strip():
        fail("the .sig must carry alg Ed25519 and a kid")


def check_manifest(product: str, channel: str, manifest: dict, args) -> None:
    expected_package = PRODUCTS[product]["packages"][channel]
    for field, want in (("schema", 1), ("app", product), ("channel", channel),
                        ("packageName", expected_package)):
        if manifest.get(field) != want:
            fail(f"manifest {field}={manifest.get(field)!r}, expected {want!r}")
    sequence = manifest.get("sequence")
    if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
        fail("manifest sequence must be a positive integer")
    urls = [manifest.get("apkUrl")] + [a.get("url") for a in manifest.get("artifacts", [])]
    for url in urls:
        parsed = urlparse(str(url))
        if parsed.scheme != "https" or (parsed.hostname or "") not in ALLOWED_HOSTS:
            fail(f"download URL not https on an allowlisted host: {url}")
    if args.expect_status and manifest.get("status") != args.expect_status:
        fail(f"status {manifest.get('status')!r} != expected {args.expect_status!r}")
    if args.expect_sequence_gt is not None and sequence <= args.expect_sequence_gt:
        fail(f"sequence {sequence} is not > {args.expect_sequence_gt}")
    print(f"manifest: app={product} channel={channel} package={expected_package} "
          f"versionCode={manifest.get('versionCode')} "
          f"versionName={manifest.get('versionName')} sequence={sequence} "
          f"status={manifest.get('status')} required={manifest.get('required')} "
          f"sizeBytes={manifest.get('sizeBytes')} sha256={manifest.get('sha256')}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--product", required=True, choices=sorted(PRODUCTS))
    parser.add_argument("--channel", required=True, choices=["production", "qa"])
    parser.add_argument("--root", default=DEFAULT_ROOT)
    parser.add_argument("--local-dir")
    parser.add_argument("--public-keys")
    parser.add_argument("--public-key-file")
    parser.add_argument("--expect-status")
    parser.add_argument("--expect-sequence-gt", type=int)
    parser.add_argument("--check-asset", action="store_true")
    parser.add_argument("--workers-repo", default=DEFAULT_REPOS["workers"])
    parser.add_argument("--fatora-repo", default=DEFAULT_REPOS["fatora"])
    parser.add_argument("--python", default=sys.executable)
    args = parser.parse_args()

    product, channel = args.product, args.channel
    keys = load_keys(args)
    name = f"{product}.json"
    if args.local_dir:
        with open(os.path.join(args.local_dir, name), "rb") as handle:
            manifest_bytes = handle.read()
        with open(os.path.join(args.local_dir, name + ".sig"), "rb") as handle:
            sig_bytes = handle.read()
        print(f"read local {os.path.join(args.local_dir, name)}(.sig)")
    else:
        root = args.root.rstrip("/")
        manifest_bytes = fetch(f"{root}/{channel}/{name}")
        sig_bytes = fetch(f"{root}/{channel}/{name}.sig")

    for label, data in (("manifest", manifest_bytes), ("sig", sig_bytes)):
        if b"\r" in data:
            fail(f"{label} contains CR bytes (line endings were converted)")
    print(f"manifest sha256={hashlib.sha256(manifest_bytes).hexdigest()} "
          f"len={len(manifest_bytes)}")

    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
        sig = json.loads(sig_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        fail(f"not UTF-8 JSON: {error}")
        return 1
    check_sig_shape(product, sig)
    check_manifest(product, channel, manifest, args)

    tool_kind = PRODUCTS[product]["tool"]
    repo = args.workers_repo if tool_kind == "workers" else args.fatora_repo
    tool = os.path.join(repo, "tool", "update", "make_manifest.py")
    if not os.path.isfile(tool):
        fail(f"app tool not found: {tool}")
    with tempfile.TemporaryDirectory(prefix="verify-manifest-") as work:
        manifest_path = os.path.join(work, name)
        sig_path = manifest_path + ".sig"
        with open(manifest_path, "wb") as handle:
            handle.write(manifest_bytes)
        with open(sig_path, "wb") as handle:
            handle.write(sig_bytes)
        command = [args.python, tool, "verify", "--manifest", manifest_path,
                   "--sig", sig_path, "--public-keys", keys]
        result = subprocess.run(command, capture_output=True, text=True)
        output = (result.stdout + result.stderr).strip()
        print(f"{tool_kind} tool verify: {output}")
        if result.returncode != 0:
            fail("the app's own verify rejected the bytes")

    if args.check_asset:
        check_asset(manifest["apkUrl"], int(manifest["sizeBytes"]))
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
