"""Value objects — immutable, compared by value, no identity of their own.

Two `Email("a@b.com")` instances are interchangeable; there is no "which one".
Value objects are a good place to centralise validation (an Email is only ever
constructed if it is well-formed). Added in later phases.
"""
