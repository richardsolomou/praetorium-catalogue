import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import publish


class PublisherTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.assets = {}
        self.storage = {}
        self.calls = []
        self.created = False
        self.corrupt_r2 = False
        for name in ["snapshot.zip", "runtime.zip"]:
            (self.directory / name).write_bytes(name.encode())
        manifest = {"sources": ["definitions"], "files": {}}
        (self.directory / "manifest.json").write_text(json.dumps(manifest))
        self.pointer = {
            "id": publish.sha256(self.directory / "manifest.json"),
            "archiveSha256": publish.sha256(self.directory / "snapshot.zip"),
            "runtime": {"archiveSha256": publish.sha256(self.directory / "runtime.zip"), "fingerprint": "a" * 64},
        }
        (self.directory / "release.json").write_text(json.dumps(self.pointer))
        (self.directory / "revocations.json").write_text(json.dumps({"format": "praetorium.catalogue-revocations.v1", "snapshots": [], "sources": []}))
        self.environment = patch.dict(os.environ, {"CLOUDFLARE_ACCOUNT_ID": "a" * 32})
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def command(self, *args, check=True):
        self.calls.append(args)
        status = 0
        output = ""
        if args[:3] == ("gh", "release", "view"):
            status = 0 if self.created else 1
            output = json.dumps({"isDraft": True})
        elif args[:3] == ("gh", "release", "create"):
            self.created = True
        elif args[:3] == ("gh", "release", "upload"):
            file = Path(args[4])
            self.assets[file.name] = file.read_bytes()
        elif args[:3] == ("gh", "release", "download"):
            name = args[args.index("--pattern") + 1]
            if name not in self.assets:
                status = 1
            else:
                (Path(args[args.index("--dir") + 1]) / name).write_bytes(self.assets[name])
        elif args[:3] == ("aws", "s3api", "head-object"):
            key = args[args.index("--key") + 1]
            status = 0 if "s3://praetorium/" + key in self.storage else 1
        elif args[:3] == ("aws", "s3", "cp"):
            source, target = args[3:5]
            if source.startswith("s3://"):
                Path(target).write_bytes(b"wrong" if self.corrupt_r2 else self.storage[source])
            else:
                self.storage[target] = Path(source).read_bytes()
        if status and check:
            raise subprocess.CalledProcessError(status, args)
        return subprocess.CompletedProcess(args, status, output, "")

    def test_repeated_publication_verifies_existing_assets_before_activation(self):
        with patch.object(publish, "run", self.command):
            publish.publish(self.directory, self.directory, True)
            publish.publish(self.directory, self.directory, True)
        self.assertEqual(sum(call[:3] == ("gh", "release", "create") for call in self.calls), 1)
        self.assertEqual(self.storage["s3://praetorium/catalogue/current.json"], (self.directory / "release.json").read_bytes())

    def test_bad_storage_readback_prevents_pointer_activation(self):
        self.corrupt_r2 = True
        with patch.object(publish, "run", self.command), self.assertRaisesRegex(ValueError, "stored artifact differs"):
            publish.publish(self.directory, self.directory, True)
        self.assertNotIn("s3://praetorium/catalogue/current.json", self.storage)

    def test_candidate_publication_leaves_discovery_unchanged(self):
        with patch.object(publish, "run", self.command):
            publish.publish(self.directory, self.directory)
        self.assertNotIn("s3://praetorium/catalogue/current.json", self.storage)
        self.assertNotIn("s3://praetorium/catalogue/revocations.json", self.storage)
        self.assertFalse(any("--latest=true" in call for call in self.calls))

    def test_mismatched_github_asset_prevents_storage_publication(self):
        self.created = True
        self.assets["snapshot.zip"] = b"wrong"
        with patch.object(publish, "run", self.command), self.assertRaisesRegex(ValueError, "GitHub mirror differs"):
            publish.publish(self.directory, self.directory, True)
        self.assertEqual(self.storage, {})

    def test_changed_archive_is_rejected_before_any_external_write(self):
        (self.directory / "snapshot.zip").write_bytes(b"wrong")
        with patch.object(publish, "run", self.command), self.assertRaisesRegex(ValueError, "snapshot.zip checksum"):
            publish.publish(self.directory, self.directory, True)
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
