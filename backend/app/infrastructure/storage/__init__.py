"""Storage adapters — concrete implementations of the StoragePort.

`LocalFileStorage` writes to the local filesystem and is used for development
and tests. A cloud (S3) implementation can be added here later behind the same
port without changing any caller.
"""
