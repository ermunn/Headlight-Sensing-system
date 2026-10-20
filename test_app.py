import importlib
import os
import sys
import types
import unittest
from unittest.mock import Mock, patch


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection
        self.lastrowid = 42
        self.results = []
        self.fetchone_result = None

    def execute(self, query, params=None):
        self.connection.queries.append((query, params))
        normalized = " ".join(query.lower().split())
        if normalized.startswith("select"):
            self.results = [
                ("UBА1234", "2026-10-11 12:00:00", 0.75, "mW/cm^2", 1.0, "Pass")
            ]
        if normalized.startswith("insert"):
            self.fetchone_result = (42,)

    def fetchall(self):
        return self.results

    def fetchone(self):
        return self.fetchone_result

    def close(self):
        pass


class FakeConnection:
    def __init__(self):
        self.queries = []
        self.committed = False

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.committed = True

    def close(self):
        pass


class MeasurementApiTest(unittest.TestCase):
    def setUp(self):
        self.connections = []

        fake_psycopg = types.SimpleNamespace()
        fake_psycopg.Error = Exception

        def connect(conninfo=None, **kwargs):
            connection = FakeConnection()
            self.connections.append(connection)
            return connection

        fake_psycopg.connect = connect
        sys.modules["psycopg"] = fake_psycopg
        os.environ["DATABASE_URL"] = "postgresql://test:test@example.com/test"

        sys.modules.pop("app", None)
        self.app_module = importlib.import_module("app")
        self.app_module.app.config["TESTING"] = True
        self.client = self.app_module.app.test_client()

    def test_photo_upload_uses_installed_blob_sdk_and_saves_metadata(self):
        image = b"\xff\xd8test-image\xff\xd9"
        blob = types.SimpleNamespace(
            url="https://example.com/photo.jpg", pathname="headlight-photos/test.jpg"
        )
        connection = Mock()
        cursor = connection.cursor.return_value
        cursor.fetchone.return_value = (7, 42, "2026-10-20 12:00:00")

        # Patch the real installed SDK function so an invalid import fails this test.
        with patch.dict(os.environ, {"PHOTO_UPLOAD_TOKEN": "test-upload-token"}), \
                patch("vercel.blob.sync.put_blob", return_value=blob) as upload, \
                patch.object(self.app_module, "get_db_connection", return_value=connection):
            response = self.client.post(
                "/api/photos", data=image, content_type="image/jpeg",
                headers={"X-Upload-Token": "test-upload-token", "X-Plate-Number": "ESP32_TEST"},
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json()["photo_url"], blob.url)
        self.assertEqual(response.get_json()["measurement_id"], 42)
        upload.assert_called_once()
        self.assertEqual(upload.call_args.args[1], image)
        self.assertEqual(upload.call_args.kwargs["access"], "public")
        self.assertEqual(cursor.execute.call_args.args[1], (
            "ESP32_TEST", "ESP32_TEST", blob.url, blob.pathname, len(image)
        ))
        connection.commit.assert_called_once()
        connection.close.assert_called_once()

    def test_sensor_post_persists_measurement_and_returns_created_payload(self):
        response = self.client.post(
            "/api/measurements",
            json={"plate_number": "UBА1234", "uv_value": 0.75},
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.get_json(),
            {
                "success": True,
                "id": 42,
                "plate_number": "UBА1234",
                "uv_value": 0.75,
                "unit": "mW/cm^2",
                "limit_value": 1.0,
                "status": "Pass",
            },
        )
        self.assertTrue(self.connections[0].committed)
        query, params = self.connections[0].queries[0]
        self.assertIn("INSERT INTO measurements", query)
        self.assertEqual(params, ("UBА1234", 0.75, "mW/cm^2", 1.0, "Pass"))

    def test_sensor_post_rejects_bad_payload_without_database_write(self):
        response = self.client.post("/api/measurements", json={"uv_value": "bad"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json(),
            {
                "success": False,
                "error": "plate_number and uv_value are required",
            },
        )
        self.assertEqual(self.connections, [])

    def test_measurements_api_returns_latest_rows_for_html_clients(self):
        response = self.client.get("/api/measurements")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            {
                "success": True,
                "measurements": [
                    {
                        "plate_number": "UBА1234",
                        "measured_at": "2026-10-11 12:00:00",
                        "uv_value": 0.75,
                        "unit": "mW/cm^2",
                        "limit_value": 1.0,
                        "status": "Pass",
                    }
                ],
            },
        )


if __name__ == "__main__":
    unittest.main()
