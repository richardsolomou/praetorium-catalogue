import argparse
import concurrent.futures
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parent.parent
REPOSITORY = "richardsolomou/praetorium-catalogue"
OBJECT_WORKERS = 16


def sha256(file):
    with open(file, "rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def run(*args, check=True):
    return subprocess.run(args, check=check, capture_output=True, text=True)


def validate_release(directory):
    pointer = json.loads((directory / "release.json").read_text())
    for value in [pointer["id"], pointer["archiveSha256"]]:
        if not re.fullmatch(r"[a-f0-9]{64}", value):
            raise ValueError("invalid release hash")
    for file, expected in [("snapshot.zip", pointer["archiveSha256"]), ("manifest.json", pointer["id"])]:
        if sha256(directory / file) != expected:
            raise ValueError(f"{file} checksum does not match")
    manifest = json.loads((directory / "manifest.json").read_text())
    policy = json.loads((directory / "revocations.json").read_text())
    if policy["format"] != "praetorium.catalogue-revocations.v1":
        raise ValueError("invalid revocation policy")
    if pointer["id"] in policy["snapshots"] or set(manifest["sources"]) & set(policy["sources"]):
        raise ValueError("cannot publish revoked catalogue")
    return pointer, manifest


def missing(error):
    return getattr(error, "response", {}).get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}


def r2_client(endpoint):
    import boto3
    from botocore.config import Config

    return boto3.client("s3", endpoint_url=endpoint, config=Config(max_pool_connections=OBJECT_WORKERS))


def publish_object(client, bucket, objects, digest):
    if not re.fullmatch(r"[a-f0-9]{64}", digest):
        raise ValueError("invalid object hash")
    file = objects / f"{digest}.gz"
    hash = hashlib.sha256()
    size = 0
    with gzip.open(file, "rb") as stream:
        while chunk := stream.read(64 * 1024):
            size += len(chunk)
            if size > 64 * 1024 * 1024:
                raise ValueError("object exceeds size limit")
            hash.update(chunk)
    if hash.hexdigest() != digest:
        raise ValueError("object checksum does not match")
    key = f"catalogue/objects/{digest}.gz"
    content = file.read_bytes()
    try:
        stored = client.head_object(Bucket=bucket, Key=key)
    except Exception as error:
        if not missing(error):
            raise
        stored = None
    if stored:
        # A single-part upload's ETag is the MD5 of its bytes; anything else is read back.
        etag = stored["ETag"].strip('"')
        if "-" not in etag:
            if stored["ContentLength"] != len(content) or etag != hashlib.md5(content).hexdigest():
                raise ValueError(f"stored artifact differs: {key}")
            return
    else:
        client.put_object(Bucket=bucket, Key=key, Body=content, ContentType="application/octet-stream", CacheControl="public, max-age=31536000, immutable")
    if client.get_object(Bucket=bucket, Key=key)["Body"].read() != content:
        raise ValueError(f"stored artifact differs: {key}")


def publish(directory, objects, activate=False, client=None):
    pointer, manifest = validate_release(directory)
    account = os.environ["CLOUDFLARE_ACCOUNT_ID"]
    if not re.fullmatch(r"[a-f0-9]{32}", account):
        raise ValueError("invalid Cloudflare account")
    endpoint = f"https://{account}.r2.cloudflarestorage.com"
    bucket = "praetorium"
    snapshot_id = pointer["id"]
    tag = f"catalogue-{snapshot_id}"
    assets = [directory / name for name in ["snapshot.zip", "manifest.json", "release.json", "revocations.json"]]
    with tempfile.TemporaryDirectory(prefix="catalogue-publish-") as temporary:
        temporary = Path(temporary)

        def s3(*args, check=True):
            return run("aws", *args, "--endpoint-url", endpoint, check=check)

        def immutable(file, key, content_type):
            present = s3("s3api", "head-object", "--bucket", bucket, "--key", key, check=False)
            destination = f"s3://{bucket}/{key}"
            if present.returncode:
                s3("s3", "cp", str(file), destination, "--content-type", content_type, "--cache-control", "public, max-age=31536000, immutable", "--only-show-errors")
            stored = temporary / hashlib.sha256(key.encode()).hexdigest()
            s3("s3", "cp", destination, str(stored), "--only-show-errors")
            if sha256(stored) != sha256(file):
                raise ValueError(f"stored artifact differs: {key}")
            stored.unlink()

        # A draft can be resumed; existing assets must match before publication.
        release = run("gh", "release", "view", tag, "--repo", REPOSITORY, "--json", "isDraft", check=False)
        draft = release.returncode != 0 or json.loads(release.stdout)["isDraft"]
        if release.returncode:
            run("gh", "release", "create", tag, "--repo", REPOSITORY, "--draft", "--target", os.environ.get("GITHUB_SHA", "feat/catalogue-releases"), "--title", f"Catalogue {tag[:12]}", "--notes", "Verified catalogue source and runtime artifacts. Application releases retain exact hashes.")
        for file in assets:
            existing = run("gh", "release", "download", tag, "--repo", REPOSITORY, "--pattern", file.name, "--dir", str(temporary), check=False)
            if existing.returncode:
                if not draft:
                    raise ValueError(f"published release is missing {file.name}")
                run("gh", "release", "upload", tag, str(file), "--repo", REPOSITORY)
                run("gh", "release", "download", tag, "--repo", REPOSITORY, "--pattern", file.name, "--dir", str(temporary))
            if sha256(temporary / file.name) != sha256(file):
                raise ValueError(f"GitHub mirror differs: {file.name}")
            (temporary / file.name).unlink()

        immutable(directory / "snapshot.zip", f"catalogue/snapshots/{snapshot_id}.zip", "application/zip")
        immutable(directory / "manifest.json", f"catalogue/manifests/{snapshot_id}.json", "application/json")
        immutable(directory / "release.json", f"catalogue/releases/{snapshot_id}.json", "application/json")

        if pointer.get("objects"):
            client = client or r2_client(endpoint)
            with concurrent.futures.ThreadPoolExecutor(max_workers=OBJECT_WORKERS) as pool:
                list(pool.map(lambda digest: publish_object(client, bucket, objects, digest), sorted(set(manifest["files"].values()))))
        if draft:
            run("gh", "release", "edit", tag, "--repo", REPOSITORY, "--draft=false", "--latest=false")
        if activate:
            run("gh", "release", "edit", tag, "--repo", REPOSITORY, "--latest=true")
            for file, key in [(directory / "revocations.json", "catalogue/revocations.json"), (directory / "release.json", "catalogue/current.json")]:
                s3("s3", "cp", str(file), f"s3://{bucket}/{key}", "--content-type", "application/json", "--cache-control", "no-store", "--only-show-errors")
                readback = temporary / file.name
                s3("s3", "cp", f"s3://{bucket}/{key}", str(readback), "--only-show-errors")
                if sha256(readback) != sha256(file):
                    raise ValueError(f"mutable publication differs: {key}")
        print(f"Verified catalogue release {tag}; discovery pointer {'activated' if activate else 'unchanged'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, default=ROOT / "build/release")
    parser.add_argument("--objects", type=Path, default=ROOT / "build/objects")
    parser.add_argument("--activate", action="store_true")
    arguments = parser.parse_args()
    publish(arguments.directory, arguments.objects, arguments.activate)
