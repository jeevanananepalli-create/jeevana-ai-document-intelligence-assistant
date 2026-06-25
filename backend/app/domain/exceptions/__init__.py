"""Domain exceptions — errors expressed in business terms, not HTTP terms.

The domain raises `DocumentNotFoundError`, not `HTTPException(404)`. The API
layer is responsible for translating domain exceptions into HTTP responses.
This keeps the domain independent of the transport mechanism. Added as needed.
"""
