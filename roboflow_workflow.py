"""Single-image client for the published Workflow recorded in the MCP contract."""

import base64
import json
import math
import os
import time
from pathlib import Path
from typing import TypedDict
from urllib.parse import urlsplit

import requests
from inference_sdk import InferenceConfiguration, InferenceHTTPClient
from inference_sdk.http.errors import HTTPClientError


CONTRACT = json.loads(Path(__file__).with_name("roboflow_workflow.json").read_text())
OUTPUT_NAMES = tuple(output["name"] for output in CONTRACT["specification"]["outputs"])
API_URL = "https://serverless.roboflow.com"


class WorkflowError(RuntimeError):
    """Base error; messages never include credentials or response payloads."""


class WorkflowConfigurationError(WorkflowError):
    pass


class WorkflowRequestError(WorkflowError):
    pass


class WorkflowResponseError(WorkflowError):
    pass


class _TransientWorkflowError(WorkflowRequestError):
    pass


class DetectionOutput(TypedDict):
    image: dict[str, int]
    predictions: list[dict]


class _TimeoutWorkflowClient(InferenceHTTPClient):
    """SDK 1.8.1 has no sync Workflow timeout option.

    Override only its request hook, retaining run_workflow response decoding.
    Keep this scoped to this client; never monkey-patch global requests state.
    The wire/auth contract is covered by test_detection.
    """

    def __init__(self, api_key):
        super().__init__(api_url=API_URL, api_key=api_key)
        self._workflow_key = api_key
        self.configure(InferenceConfiguration(
            api_key_transport="header", workflow_run_retries_enabled=False,
        ))

    def _execute_workflow_request(self, *, workspace_name, workflow_id,
                                  images, parameters, **options):
        image = images["image"]
        image_type = "url" if image.startswith("https://") else "base64"
        try:
            response = requests.post(
                f"{API_URL}/{workspace_name}/workflows/{workflow_id}",
                headers={"Authorization": f"Bearer {self._workflow_key}"},
                json={"inputs": {"image": {"type": image_type, "value": image},
                                  **parameters}},
                timeout=(5, 15), allow_redirects=False,
            )
        except (requests.Timeout, requests.ConnectionError):
            raise _TransientWorkflowError("Workflow connection failed or timed out") from None
        status = response.status_code
        if status in (408, 429) or 500 <= status <= 599:
            response.close()
            raise _TransientWorkflowError(f"Workflow temporarily unavailable (HTTP {status})")
        if status != 200:
            response.close()
            raise WorkflowRequestError(f"Workflow request rejected (HTTP {status})")
        return response


def _parse_outputs(result) -> list[dict[str, DetectionOutput]]:
    if not isinstance(result, list) or len(result) != 1:
        raise WorkflowResponseError("Expected one Workflow result for one image")
    entry = result[0]
    if not isinstance(entry, dict) or not all(name in entry for name in OUTPUT_NAMES):
        raise WorkflowResponseError("Workflow output keys differ from the MCP contract")
    cleaned = {}
    for name in OUTPUT_NAMES:
        output = entry[name]
        if not isinstance(output, dict) or not isinstance(output.get("predictions"), list):
            raise WorkflowResponseError("Expected a detection output envelope")
        image = output.get("image")
        if not isinstance(image, dict) or any(
            type(image.get(field)) is not int or image[field] <= 0
            for field in ("width", "height")
        ):
            raise WorkflowResponseError("Invalid detection image dimensions")
        boxes = []
        for box in output["predictions"]:
            if not isinstance(box, dict) or not isinstance(box.get("class"), str):
                raise WorkflowResponseError("Invalid detection class")
            for field in ("x", "y", "width", "height", "confidence"):
                value = box.get(field)
                if type(value) not in (float, int) or not math.isfinite(value):
                    raise WorkflowResponseError("Invalid detection coordinates/confidence")
            if not 0 <= box["confidence"] <= 1 or box["width"] < 0 or box["height"] < 0:
                raise WorkflowResponseError("Detection values outside valid bounds")
            # Only retain fields consumed by the upload API; discard polygon points.
            boxes.append({field: box[field] for field in (
                "x", "y", "width", "height", "confidence", "class",
            )})
        cleaned[name] = {"image": {field: image[field] for field in ("width", "height")},
                         "predictions": boxes}
    return [cleaned]


def run_plate_workflow(image: bytes | str | Path) -> list[dict[str, DetectionOutput]]:
    """Run one JPEG/image, local path, or HTTPS URL; retry transient failures twice.

    The MCP contract declares no runtime parameters and no image outputs.
    Unexpected output shapes fail closed rather than returning large blobs.
    """
    key = os.getenv("ROBOFLOW_API_KEY", "").strip()
    if not key:
        raise WorkflowConfigurationError("Set ROBOFLOW_API_KEY in the server environment")
    if isinstance(image, str) and urlsplit(image).scheme in ("http", "https"):
        if urlsplit(image).scheme != "https" or not urlsplit(image).netloc:
            raise WorkflowConfigurationError("Image URLs must use HTTPS")
        encoded = image
    else:
        try:
            data = image if isinstance(image, bytes) else Path(image).read_bytes()
        except (OSError, TypeError, ValueError):
            raise WorkflowConfigurationError("Image path could not be read") from None
        if not data or len(data) > 4_400_000:
            raise WorkflowConfigurationError("Image must contain 1 to 4,400,000 bytes")
        encoded = base64.b64encode(data).decode("ascii")
    client = _TimeoutWorkflowClient(key)
    for attempt in range(3):
        try:
            result = client.run_workflow(
                workspace_name=CONTRACT["workspace_name"],
                workflow_id=CONTRACT["workflow_id"],
                images={"image": encoded}, parameters={},
            )
            return _parse_outputs(result)
        except _TransientWorkflowError:
            pass
        except (KeyError, TypeError, ValueError):
            raise WorkflowResponseError("Workflow returned malformed JSON or outputs") from None
        except (requests.RequestException, HTTPClientError):
            raise WorkflowRequestError("Workflow request failed") from None
        if attempt < 2:
            time.sleep(0.5 * (2 ** attempt))
    raise WorkflowRequestError("Workflow unavailable after three attempts (timeout/network/server)")
