import re

from whitenoise.storage import CompressedManifestStaticFilesStorage


class ManifestStorage(CompressedManifestStaticFilesStorage):
    FILE_IGNORE_PATTERN = re.compile(r"\.hash-[a-f0-9]{8}\.(?:js|css)$", re.IGNORECASE)

    def hashed_name(self, name, *args, **kwargs):
        # Files generated by Vite already have a hexadecimal-content hash,
        # and it’s important that we don’t re-hash these files as they might
        # reference each other.
        if re.search(self.FILE_IGNORE_PATTERN, name):
            return name
        return super().hashed_name(name, *args, **kwargs)
