"""Application layer — orchestrates domain objects to fulfil use cases.

Knows about workflows ("to register a user: validate, hash password, persist"),
but not about HTTP or the database engine. It depends on domain interfaces,
which are resolved to concrete infrastructure at startup (dependency injection).
"""
