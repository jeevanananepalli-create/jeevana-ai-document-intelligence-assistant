"""Domain layer — pure business concepts with ZERO framework imports.

This is the innermost layer. It must never import FastAPI, SQLAlchemy, or any
other infrastructure. If `grep -r "sqlalchemy" app/domain/` ever returns a
match, the architecture has been violated.

Sub-packages:
- entities:      objects with identity and a lifecycle (e.g. User, Document).
- value_objects: immutable values compared by their contents (e.g. Email).
- exceptions:    domain-specific errors, independent of HTTP/transport.
- interfaces:    abstract "ports" (Protocols) the domain depends on, implemented
                 by the infrastructure layer.
"""
