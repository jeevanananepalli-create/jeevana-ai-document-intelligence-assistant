"""API layer — the HTTP edge of the application.

Translates HTTP requests into use-case calls and use-case results into HTTP
responses (status codes, JSON, headers). It is the only layer that knows the
application is exposed over HTTP. Versioned sub-packages (v1, v2, ...) allow the
contract to evolve without breaking existing clients.
"""
