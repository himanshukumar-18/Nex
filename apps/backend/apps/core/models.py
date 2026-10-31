"""
NEX Core — Abstract Base Models and Database Conventions.

Every persistent entity in NEX should inherit from BaseModel or TimeStampedModel
to guarantee consistent primary key, auditing, and indexing behavior across all apps.
"""

import uuid

from django.db import models


class TimeStampedModel(models.Model):
    """
    Abstract model providing automatic timestamp auditing fields.

    Conventions:
      - `created_at`: Set once when the record is created. Indexed for chronology.
      - `updated_at`: Automatically updated on each save. Indexed for freshness.
    """

    created_at = models.DateTimeField(
        auto_now_add=True,
        editable=False,
        db_index=True,
        help_text="Timestamp when this record was created.",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        editable=False,
        db_index=True,
        help_text="Timestamp when this record was last modified.",
    )

    class Meta:
        abstract = True
        ordering = ["-created_at"]


class BaseModel(TimeStampedModel):
    """
    Standard abstract base model for all primary business entities.

    Conventions:
      1. Primary Key: UUIDv4 (`id`) to prevent sequential ID harvesting,
         support offline/distributed generation, and avoid cross-tenant enumeration.
      2. Auditing: Inherits `created_at` and `updated_at` from TimeStampedModel.
      3. Immutability: Primary key is immutable and non-editable.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier (UUIDv4) for this record.",
    )

    class Meta:
        abstract = True
        ordering = ["-created_at"]

