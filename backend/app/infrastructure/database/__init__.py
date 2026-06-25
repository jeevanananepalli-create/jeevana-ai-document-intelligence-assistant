"""Database infrastructure — SQLAlchemy engine, session factory, and Base.

Owns the connection to PostgreSQL and the machinery for handing out database
sessions. Repositories (in the sibling `repositories` package) use these
sessions to read and write data.
"""
