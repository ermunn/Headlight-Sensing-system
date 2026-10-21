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
