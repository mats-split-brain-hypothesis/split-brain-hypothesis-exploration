"""Release check: the package version must match the latest release tag (vX.Y.Z)."""
import subprocess

import ledgerfx


def test_version_matches_latest_tag():
    tag = subprocess.run(["git", "describe", "--tags", "--abbrev=0"], capture_output=True, text=True,
                         check=True).stdout.strip()
    assert tag == f"v{ledgerfx.__version__}"
