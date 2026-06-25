"""Application package root.

The internal structure follows Clean Architecture. Dependencies always point
inward: api -> application -> domain, and infrastructure -> domain. The domain
layer never imports from any outer layer, which keeps business logic pure and
testable without a database, network, or web framework.
"""
