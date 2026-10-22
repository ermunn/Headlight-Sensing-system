# ESP32 voltage and photo capture

The ESP32 sends one `POST /api/captures` request:

- `Content-Type: image/jpeg`
- `X-LDR-Value: 2.100` (voltage, finite and between 0 and 3.3 V)
- `X-Upload-Token: <device upload token>`
- Body: raw JPEG bytes, maximum 4,400,000 bytes.

The server stores voltage using the existing `uv_value` database column for
compatibility, with unit `V` and the server's `DEFAULT_LIMIT_VALUE` (currently
2.000 V). Values strictly above the limit are `Fail`; others are `Pass`.
Historical measurements keep their original units and values.

The web table displays measurement dates in Ulaanbaatar time (UTC+8), with
seconds precision. Database timestamps and API timestamp offsets are preserved;
only the table presentation is converted. Legacy timestamps without an offset
are treated as UTC for display.

The photo and measurement are inserted in one database transaction and linked
by the new measurement ID. No plate number is sent by the ESP32. The older
`/api/measurements` and `/api/photos` interfaces remain available.

## Configuration

1. Set Vercel `DATABASE_URL`, `BLOB_READ_WRITE_TOKEN`, and `PHOTO_UPLOAD_TOKEN`.
   The Blob store must support private blobs, as used by the photo viewer.
2. Optionally set `PLATE_RECOGNIZER_TOKEN` to enable Plate Recognizer Snapshot
   Cloud recognition. Images are sent to that service only when this is configured.
   See https://guides.platerecognizer.com/docs/snapshot/api-reference/ .
3. Redeploy the backend before uploading the updated ESP32 firmware.
4. Copy `esp32_sensor/secrets.example.h` to `esp32_sensor/secrets.h` and set
   `PHOTO_UPLOAD_TOKEN` to the same upload token as Vercel. This file is ignored
   by Git. Keep real tokens out of tracked files.
5. Compile and flash `esp32_sensor/esp32_sensor.ino` with its existing libraries.

Without an OCR token, on OCR failure, with multiple detected plates, or when
the single result has confidence below 0.8, the plate is stored as
`Танигдаагүй`. The API returns `recognition_status` to distinguish these cases.
Recognition accuracy for actual Mongolian plates needs hardware/photo testing.

## Verification

Run `python -m unittest test_captures -v` for isolated tests with mocked services.
On hardware, cross the existing 2.0 V trigger after rearming at or below 1.9 V.
Serial Monitor should show HTTP 201 and a measurement ID. Refresh the website
and check that the same row has the voltage, unit `V`, and its photo.

If Blob upload succeeds but the database fails, the API returns 500 and the
database transaction rolls back; an unused Blob can remain. Do not blindly
retry ambiguous timeouts: this endpoint does not yet deduplicate requests.

## Roboflow plate detection

Both photo endpoints run the published single-image Workflow before storage.
`roboflow_workflow.py` exposes `run_plate_workflow(image)` for image bytes, a
local image path, or an HTTPS URL. The return value is a list containing one
dictionary per image, keyed by the output names in `roboflow_workflow.json`.
The current Workflow only locates plates; Plate Recognizer still supplies OCR.

Setup uses the existing Python environment and dotenv configuration:

1. Install the runtime dependencies from `requirements.txt` in your existing
   environment. The Workflow client uses lightweight `requests` HTTP calls.
   Do not add `inference-sdk` to the Vercel runtime: its native vision dependencies
   (including OpenCV and NumPy) caused a 612.81 MB bundle exceeding the deployment
   limit. Model execution stays on Roboflow; no local vision libraries are needed.
2. Set `ROBOFLOW_API_KEY` in the local ignored `.env` or in Vercel environment
   variables. Obtain it at https://app.roboflow.com/settings/api . Never put
   this key in firmware, frontend code, URLs, logs, or request bodies.
3. Redeploy to apply the server configuration. `ROBOFLOW_MODEL_ID` is no longer
   used; the workspace and Workflow slug come from the checked-in MCP contract.

The published Workflow is
`emukazol-gmail-com/mongolian-plate-vmongolian-plate-fbyll-1-rfdetr-small-t1-logic`.
Its exact inputs and outputs were fetched through Roboflow MCP `workflows_get`:
one `InferenceImage` named `image`, no runtime parameters, and one `JsonField`
output named `predictions`. The real output is
`[{"predictions": {"image": {"width": 1200, "height": 675}, "predictions": [...]}}]`.
The MCP response fixture is `tests/fixtures/roboflow_workflow_response.json`.
Its source is the user-selected sample image:
https://soyacincau.com/wp-content/uploads/2024/09/malaysia-ev-plate-jpjeplate02.jpg .
This Malaysian sample verifies the integration, not accuracy on Mongolian plates.

Authentication uses only `Authorization: Bearer`. The client posts JSON to the
published Workflow endpoint and reads the REST response's `outputs` list.
This preserves the MCP-grounded contract without bundling the inference SDK.
The HTTP connect/read timeouts are 5/15 seconds per attempt. Timeouts, connection
failures, HTTP 408/429 and 5xx responses retry twice, waiting 0.5 then 1 second.
These are socket timeouts, not a total wall-clock deadline; allow for all three
attempts plus OCR and storage when configuring deployment request duration.
No build or deployment settings were changed for this integration.

The client raises `WorkflowConfigurationError`, `WorkflowRequestError`, or
`WorkflowResponseError`. The upload API keeps its existing `not_configured`,
`detected`, `not_detected`, and `unavailable` detection statuses; inference
failure does not block saving a photo. Only box coordinates, class and confidence
are returned to the caller; raw polygon points and unused metadata are discarded.
There are no image outputs in the current contract. Unexpected image-shaped
output fails validation and is never logged or returned as a base64 payload.

Run isolated regression tests:

```powershell
python -m unittest test_detection test_captures -v
```

Run the real, billable single-image smoke test with the configured API key:

```powershell
$env:ROBOFLOW_SMOKE_IMAGE = 'https://soyacincau.com/wp-content/uploads/2024/09/malaysia-ev-plate-jpjeplate02.jpg'
python -m unittest test_detection.WorkflowSmokeTest -v
Remove-Item Env:ROBOFLOW_SMOKE_IMAGE
```

For future developers and coding agents: before changing this integration,
fetch the published definition with MCP `workflows_get`, then run
`workflows_run` on an approved sample. Refresh the contract and response fixture
from those results; do not guess output names or add undeclared parameters.
Keep header-only auth, bounded retries, and the upload failure fallback.
Keep the hosted HTTP client free of local inference dependencies. If image
outputs are added, decode them into safely named files rather than logging
or returning base64. Video requires a separately chosen WebRTC integration.
No README or coding-agent instruction files existed in this repository at
integration time; this existing setup document also provides developer guidance.

After changing dependencies, redeploy in Vercel with **Use existing Build Cache**
disabled so dependencies are resolved from the updated `requirements.txt`.
Check the new build's function bundle size; the final deployed size must be
verified by Vercel. Increasing function memory does not reduce bundle size.
