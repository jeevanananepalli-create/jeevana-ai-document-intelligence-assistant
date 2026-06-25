"""Infrastructure layer — concrete implementations of domain interfaces.

This is where the real I/O lives: databases, file storage, and external APIs.
Everything here is replaceable. Swapping PostgreSQL for another store, or a
local model for a cloud API, means writing a new implementation here and
changing nothing in the domain or application layers.
"""
