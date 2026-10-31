"""
Tests for NEX Core database foundation and health endpoints.
"""

import uuid
from django.db import connection
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from apps.core.models import BaseModel, TimeStampedModel


class DatabaseFoundationTests(TestCase):
    """Verify PostgreSQL connectivity and pgvector capabilities."""

    def test_database_connection(self) -> None:
        """Confirm database connection can be established."""
        connection.ensure_connection()
        self.assertTrue(connection.is_usable())

    def test_pgvector_extension_installed(self) -> None:
        """Confirm the pgvector extension is enabled in PostgreSQL."""
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';"
            )
            row = cursor.fetchone()
            self.assertIsNotNone(row, "pgvector extension is not registered in pg_extension")
            self.assertEqual(row[0], "vector")

    def test_vector_euclidean_distance(self) -> None:
        """Verify vector Euclidean distance operator (<->) works correctly."""
        with connection.cursor() as cursor:
            cursor.execute("SELECT '[1,2,3]'::vector <-> '[4,5,6]'::vector;")
            result = cursor.fetchone()[0]
            self.assertAlmostEqual(result, 5.1961524, places=5)

    def test_vector_cosine_distance(self) -> None:
        """Verify vector Cosine distance operator (<=>) works correctly."""
        with connection.cursor() as cursor:
            cursor.execute("SELECT '[1,0,0]'::vector <=> '[0,1,0]'::vector;")
            result = cursor.fetchone()[0]
            self.assertAlmostEqual(result, 1.0, places=5)


class ModelConventionsTests(SimpleTestCase):
    """Verify abstract model architecture conventions."""

    def test_base_model_is_abstract(self) -> None:
        """BaseModel must be abstract so it does not create a database table."""
        self.assertTrue(BaseModel._meta.abstract)

    def test_timestamped_model_is_abstract(self) -> None:
        """TimeStampedModel must be abstract."""
        self.assertTrue(TimeStampedModel._meta.abstract)

    def test_base_model_fields(self) -> None:
        """BaseModel must declare id (UUIDv4), created_at, and updated_at."""
        field_names = [f.name for f in BaseModel._meta.fields]
        self.assertIn("id", field_names)
        self.assertIn("created_at", field_names)
        self.assertIn("updated_at", field_names)


class HealthEndpointTests(TestCase):
    """Verify liveness and readiness probe behaviors."""

    def test_liveness_endpoint(self) -> None:
        """Liveness endpoint must return HTTP 200 with ok status."""
        response = self.client.get(reverse("health_liveness"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("status"), "ok")

    def test_liveness_alias_endpoint(self) -> None:
        """Liveness alias /health/live/ must return HTTP 200."""
        response = self.client.get(reverse("health_liveness_alias"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("status"), "ok")

    def test_readiness_endpoint_success(self) -> None:
        """Readiness endpoint must return HTTP 200 when database is healthy."""
        response = self.client.get(reverse("health_readiness"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("status"), "ready")
        self.assertEqual(data.get("database"), "connected")

