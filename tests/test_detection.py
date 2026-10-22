import copy
import json
import os
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

import requests
import app
import roboflow_workflow as workflow

SAMPLE = json.loads(Path(__file__).parent.joinpath(
    "fixtures/roboflow_workflow_response.json").read_text())


def response(status=200, outputs=None):
    return Mock(status_code=status, json=Mock(return_value={
        "outputs": copy.deepcopy(SAMPLE if outputs is None else outputs),
    }))


class DetectionTest(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {"ROBOFLOW_API_KEY": "test-key"})
        env.start()
        self.addCleanup(env.stop)

    def test_http_wire_contract_and_real_response(self):
        with patch.object(workflow.requests, "post", return_value=response()) as send:
            result = workflow.run_plate_workflow(b"jpeg")
        self.assertEqual(set(result[0]), set(workflow.OUTPUT_NAMES))
        box = result[0][workflow.OUTPUT_NAMES[0]]["predictions"][0]
        self.assertEqual(box["class"], "license plate")
        self.assertAlmostEqual(box["confidence"], 0.9618217349052429)
        self.assertEqual(send.call_args.args[0],
                         f"{workflow.API_URL}/{workflow.CONTRACT['workspace_name']}/workflows/"
                         f"{workflow.CONTRACT['workflow_id']}")
        options = send.call_args.kwargs
        self.assertEqual(options["headers"], {"Authorization": "Bearer test-key"})
        self.assertEqual(options["json"], {"inputs": {"image": {"type": "base64", "value": "anBlZw=="}}})
        self.assertEqual(options["timeout"], (5, 15))
        self.assertFalse(options["allow_redirects"])

    def test_https_input_and_no_polygons(self):
        outputs = copy.deepcopy(SAMPLE)
        outputs[0][workflow.OUTPUT_NAMES[0]]["predictions"][0]["points"] = [1, 2]
        with patch.object(workflow.requests, "post", return_value=response(outputs=outputs)) as send:
            result = workflow.run_plate_workflow("https://example.com/plate.jpg")
        self.assertEqual(send.call_args.kwargs["json"]["inputs"]["image"]["type"], "url")
        self.assertNotIn("points", result[0][workflow.OUTPUT_NAMES[0]]["predictions"][0])

    def test_timeout_retries_twice(self):
        with patch.object(workflow.requests, "post", side_effect=requests.Timeout) as send, \
                patch.object(workflow.time, "sleep") as sleep:
            with self.assertRaises(workflow.WorkflowRequestError):
                workflow.run_plate_workflow(b"jpeg")
        self.assertEqual(send.call_count, 3)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [0.5, 1.0])

    def test_server_retry_recovers_and_auth_failure_does_not_retry(self):
        with patch.object(workflow.requests, "post", side_effect=[response(503), response()]) as send, \
                patch.object(workflow.time, "sleep"):
            workflow.run_plate_workflow(b"jpeg")
            self.assertEqual(send.call_count, 2)
        with patch.object(workflow.requests, "post", return_value=response(401)) as send:
            with self.assertRaises(workflow.WorkflowRequestError):
                workflow.run_plate_workflow(b"jpeg")
            self.assertEqual(send.call_count, 1)

    def test_malformed_output_rejected(self):
        for outputs in ([], [{}], [{workflow.OUTPUT_NAMES[0]: {"predictions": "bad"}}]):
            with self.subTest(outputs=outputs), \
                    patch.object(workflow.requests, "post", return_value=response(outputs=outputs)):
                with self.assertRaises(workflow.WorkflowResponseError):
                    workflow.run_plate_workflow(b"jpeg")

    def test_missing_key_and_http_url_never_send(self):
        with patch.object(workflow.requests, "post") as send:
            with self.assertRaises(workflow.WorkflowConfigurationError):
                workflow.run_plate_workflow("http://example.com/image.jpg")
            with patch.dict(os.environ, {"ROBOFLOW_API_KEY": ""}):
                self.assertEqual(app.detect_plate(b"jpeg")["status"], "not_configured")
                with self.assertRaises(workflow.WorkflowConfigurationError):
                    workflow.run_plate_workflow(b"jpeg")
            send.assert_not_called()

    def test_app_preserves_api_and_fallback(self):
        with patch.object(workflow.requests, "post", return_value=response()):
            result = app.detect_plate(b"jpeg")
        self.assertEqual(result["status"], "detected")
        self.assertEqual(len(result["predictions"]), 1)
        with patch.object(workflow, "run_plate_workflow", side_effect=workflow.WorkflowRequestError):
            self.assertEqual(app.detect_plate(b"jpeg"), {"status": "unavailable", "predictions": []})


class WorkflowSmokeTest(unittest.TestCase):
    @unittest.skipUnless(os.getenv("ROBOFLOW_SMOKE_IMAGE"), "Set ROBOFLOW_SMOKE_IMAGE for live inference")
    def test_live_sample_output_keys(self):
        result = workflow.run_plate_workflow(os.environ["ROBOFLOW_SMOKE_IMAGE"])
        self.assertEqual(len(result), 1)
        self.assertTrue(set(workflow.OUTPUT_NAMES).issubset(result[0]))


if __name__ == "__main__":
    unittest.main()
