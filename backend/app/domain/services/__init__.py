"""Domain services — pure business logic that doesn't belong to a single entity.

A domain service holds logic that operates on domain concepts but isn't a
natural method on one entity. `TextChunker` is the first: splitting text into
retrievable chunks is a core business rule, has no I/O, and is fully unit
testable. (Application *services*, which orchestrate use cases, live separately
under `app.application.services`.)
"""
