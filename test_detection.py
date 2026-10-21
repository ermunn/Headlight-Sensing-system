import base64
import io
import json
import os
import unittest
from unittest.mock import patch

import app


class DetectionTest(unittest.TestCase):
    def test_http_detection_preserves_predictions(self):
        predictions = [{"class": "plate", "confidence": 0.95}]
        with patch.dict(os.environ, {"ROBOFLOW_API_KEY": "test-key",
                                     "ROBOFLOW_MODEL_ID": "project/model-1"}), \
                patch.object(app, "urlopen") as send:
            send.return_value.__enter__.return_value = io.BytesIO(
                json.dumps({"predictions": predictions}).encode()
            )
            result = app.detect_plate(b"jpeg-bytes")
        self.assertEqual(result, {"status": "detected", "predictions": predictions})
        request = send.call_args.args[0]
        self.assertEqual(request.full_url, "https://serverless.roboflow.com/project/model-1")
        self.assertEqual(request.data, base64.b64encode(b"jpeg-bytes"))
        self.assertEqual(request.get_header("Authorization"), "Bearer test-key")
        self.assertEqual(send.call_args.kwargs["timeout"], 15)

    def test_missing_key_skips_network(self):
        with patch.dict(os.environ, {"ROBOFLOW_API_KEY": ""}), \
                patch.object(app, "urlopen") as send:
            self.assertEqual(app.detect_plate(b"jpeg")["status"], "not_configured")
            send.assert_not_called()

    def test_failure_does_not_block_photo_storage(self):
        with patch.dict(os.environ, {"ROBOFLOW_API_KEY": "test-key"}), \
                patch.object(app, "urlopen", side_effect=TimeoutError):
            self.assertEqual(app.detect_plate(b"jpeg"),
                             {"status": "unavailable", "predictions": []})


if __name__ == "__main__":
    unittest.main()
