"""
Migration to enable the pgvector extension in PostgreSQL.

Uses Django's CreateExtension operation which safely executes:
    CREATE EXTENSION IF NOT EXISTS "vector";

This operation is idempotent, safe on existing databases, and reversible.
"""

from django.contrib.postgres.operations import CreateExtension
from django.db import migrations


class Migration(migrations.Migration):
    """Enable vector extension for AI code intelligence and semantic retrieval."""

    initial = True

    dependencies: list[tuple[str, str]] = []

    operations = [
        CreateExtension("vector"),
    ]

