import os
import uuid

def sanitize_filename(filename: str) -> str:
    """Sanitizes a filename to prevent directory traversal and other issues."""
    return os.path.basename(filename)

def get_unique_filename(filename: str) -> str:
    """Generates a unique filename to avoid collisions."""
    ext = ""
    if "." in filename:
        ext = filename.rsplit(".", 1)[1]
    return f"{uuid.uuid4()}.{ext}"
