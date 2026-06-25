"""Repositories — concrete data access implementing domain interfaces.

A repository hides SQL behind a collection-like interface (get, add, list).
The application layer talks to the repository *interface* (a Protocol in
app.domain.interfaces), never to SQLAlchemy directly. Added in later phases.
"""
