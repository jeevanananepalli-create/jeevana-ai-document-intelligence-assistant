"""Interfaces (ports) — abstract contracts the domain depends on.

Defined as `typing.Protocol` classes: they describe *what* the domain needs
(e.g. "a UserRepository can get a user by email") without saying *how* it is
done. The infrastructure layer provides concrete implementations. This is the
Dependency Inversion Principle and what makes implementations swappable.
"""
