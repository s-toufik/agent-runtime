from importlib.metadata import PackageMetadata, metadata

APPLICATION_NAME: str = "agent-runtime"
_METADATA: PackageMetadata = metadata(APPLICATION_NAME)
APPLICATION_VERSION: str = _METADATA.get("version", "X.X.X")
APPLICATION_AUTHORS: str = _METADATA.get("Author-email", "N/A")
