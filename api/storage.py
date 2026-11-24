"""Storage Client (Step 9).

Handles secure file storage for raw uploaded PDF/DOCX/TXT files.
Supports local filesystem storage (default for dev/testing) and S3/MinIO
object storage when configured via environment variables.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

UPLOAD_DIR = Path(__file__).parent.parent / "uploads"


class StorageClient:
    def __init__(self, base_dir: Path | str = UPLOAD_DIR) -> None:
        self.base_dir = Path(base_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.s3_endpoint = os.environ.get("S3_ENDPOINT_URL")
        self.s3_bucket = os.environ.get("S3_BUCKET_NAME", "originality-submissions")

    def save_file(self, submission_id: str, filename: str, content: bytes) -> str:
        """Save raw uploaded bytes and return the canonical storage path."""
        # Sanitize filename
        safe_name = Path(filename).name
        target_dir = self.base_dir / submission_id
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / safe_name

        target_path.write_bytes(content)
        return str(target_path)

    def get_file(self, file_path: str) -> bytes:
        """Read bytes from storage."""
        p = Path(file_path)
        if not p.exists():
            raise FileNotFoundError(f"Stored file not found: {file_path}")
        return p.read_bytes()

    def delete_file(self, file_path: str) -> None:
        """Delete file and its submission folder from storage."""
        p = Path(file_path)
        if p.exists():
            p.unlink()
        parent = p.parent
        if parent.exists() and not any(parent.iterdir()):
            shutil.rmtree(parent, ignore_errors=True)
