import os
import re
import hmac
import uuid
import math
import json
import base64
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

from urllib.request import Request, urlopen
from urllib.parse import urlencode

from flask import (
    Flask, render_template, request, redirect, jsonify, Response, abort
)
import psycopg

app = Flask(__name__)

DEFAULT_UNIT = "mW/cm^2"
DEFAULT_LIMIT_VALUE = 2.000



def get_db_connection():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable is not set")
    return psycopg.connect(database_url)


def measurement_status(uv_value, limit_value):
    if uv_value > limit_value:
        return "Fail"
    return "Pass"


def measurement_to_dict(row):
    return {
        "plate_number": row[0],
        "measured_at": str(row[1]),
        "uv_value": float(row[2]),
        "unit": row[3],
        "limit_value": float(row[4]),
        "status": row[5]
    }
 
def fetch_measurements():
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT m.plate_number,
                   m.measured_at,
                   m.uv_value,
                   m.unit,
                   m.limit_value,
                   m.status,
                   (SELECT p.id FROM photos p
                    WHERE p.measurement_id = m.id
                    ORDER BY p.captured_at DESC LIMIT 1)
            FROM measurements m
            ORDER BY m.measured_at DESC
        """)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()


def insert_measurement(plate_number, uv_value, unit=DEFAULT_UNIT, limit_value=DEFAULT_LIMIT_VALUE):
    status = measurement_status(uv_value, limit_value)
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT INTO measurements
            (plate_number, measured_at, uv_value, unit, limit_value, status)
            VALUES (%s, NOW(), %s, %s, %s, %s)
            RETURNING id
        """, (
            plate_number,
            uv_value,
            unit,
            limit_value,
            status
        ))

        measurement_id = cursor.fetchone()[0]
        conn.commit()
    finally:
        cursor.close()
        conn.close()

    return {
        "id": measurement_id,
        "plate_number": plate_number,
        "uv_value": uv_value,
        "unit": unit,
        "limit_value": limit_value,
        "status": status
    }


def detect_plate(image_bytes):
    """Locate plates with the published Workflow; failures do not block storage."""
    api_key = os.getenv("ROBOFLOW_API_KEY", "").strip()
    if not api_key:
        return {"status": "not_configured", "predictions": []}

    try:
        from roboflow_workflow import run_plate_workflow, OUTPUT_NAMES

        result = run_plate_workflow(image_bytes)
        predictions = [box for name in OUTPUT_NAMES
                       for box in result[0][name]["predictions"]]
        return {
            "status": "detected" if predictions else "not_detected",
            "predictions": predictions,
        }
    except Exception:
        app.logger.warning("Roboflow Workflow unavailable; saving photo")
        return {"status": "unavailable", "predictions": []}


@app.route("/")
def home():
    try:
        measurements = fetch_measurements()
    except (psycopg.Error, RuntimeError) as error:
        return f"Database error: {error}", 500

    return render_template("index.html", measurements=measurements)


def recognize_plate(image_bytes):
    """Optional server-side OCR; capture remains available if recognition fails."""
    token = os.getenv("PLATE_RECOGNIZER_TOKEN", "").strip()
    if not token:
        return "Танигдаагүй", "not_configured"
    try:
        payload = urlencode({"upload": base64.b64encode(image_bytes).decode("ascii")}).encode()
        ocr_request = Request(
            "https://api.platerecognizer.com/v1/plate-reader/",
            data=payload,
            headers={"Authorization": f"Token {token}", "Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with urlopen(ocr_request, timeout=10) as response:
            results = json.load(response).get("results", [])
        if len(results) != 1:
            return "Танигдаагүй", "not_recognized"
        result = results[0]
        plate = str(result.get("plate", "")).strip().upper()
        if not plate or len(plate) > 64 or float(result.get("score", 0)) < 0.8:
            return "Танигдаагүй", "not_recognized"
        return plate, "recognized"
    except Exception:
        app.logger.warning("Plate recognition unavailable; saving unrecognized capture")
        return "Танигдаагүй", "unavailable"


@app.route("/api/captures", methods=["POST"])
@app.route("/api/photos", methods=["POST"])
def api_upload_photo():
    """Store a raw JPEG in Vercel Blob and link it to the plate's latest measurement."""
    expected_token = os.getenv("PHOTO_UPLOAD_TOKEN", "")
    provided_token = request.headers.get("X-Upload-Token", "")
    if not expected_token:
        return jsonify({"success": False, "error": "Photo uploads are not configured"}), 503
    if not hmac.compare_digest(provided_token, expected_token):
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    content_type = request.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
    if content_type != "image/jpeg":
        return jsonify({"success": False, "error": "Content-Type must be image/jpeg"}), 415

    is_capture = request.path == "/api/captures"
    voltage = None
    if is_capture:
        try:
            voltage = float(request.headers.get("X-LDR-Value", ""))
        except (TypeError, ValueError):
            return jsonify({"success": False, "error": "X-LDR-Value must be voltage in V"}), 400
        if not math.isfinite(voltage) or not 0 <= voltage <= 3.3:
            return jsonify({"success": False, "error": "Voltage must be between 0 and 3.3 V"}), 400
    plate_number = request.headers.get("X-Plate-Number", "").strip()
    if not is_capture and (not plate_number or len(plate_number) > 64):
        return jsonify({"success": False, "error": "A valid X-Plate-Number header is required"}), 400

    max_photo_bytes = 4_400_000
    if request.content_length is not None and request.content_length > max_photo_bytes:
        return jsonify({"success": False, "error": "JPEG must be smaller than 4.4 MB"}), 413

    image_bytes = request.get_data(cache=False)
    if len(image_bytes) < 4 or len(image_bytes) > max_photo_bytes:
        return jsonify({"success": False, "error": "JPEG is empty or exceeds the 4.4 MB limit"}), 413
    if not image_bytes.startswith(b"\xff\xd8") or not image_bytes.endswith(b"\xff\xd9"):
        return jsonify({"success": False, "error": "Request body is not a valid JPEG"}), 400

    # Run detection for both photo upload endpoints.
    detection = detect_plate(image_bytes)
    if is_capture:
        plate_number, recognition_status = recognize_plate(image_bytes)

    try:
        from vercel.blob.sync import put_blob

        plate_slug = re.sub(r"[^A-Za-z0-9_-]+", "_", plate_number)[:64] or "unknown"
        pathname = f"headlight-photos/{plate_slug}/{uuid.uuid4().hex}.jpg"
        blob = put_blob(
            pathname,
            image_bytes,
            access="private",
            content_type="image/jpeg",
            add_random_suffix=True,
        )
    except Exception:
        app.logger.exception("Photo upload to Vercel Blob failed")
        return jsonify({"success": False, "error": "Could not store photo"}), 502

    try:
        with get_db_connection() as conn:
            with conn.cursor() as cursor:
                if is_capture:
                    cursor.execute("""
                        INSERT INTO measurements
                        (plate_number, measured_at, uv_value, unit, limit_value, status)
                        VALUES (%s, NOW(), %s, 'V', %s, %s) RETURNING id
                    """, (plate_number, voltage, DEFAULT_LIMIT_VALUE,
                          measurement_status(voltage, DEFAULT_LIMIT_VALUE)))
                    measurement_id = cursor.fetchone()[0]
                else:
                    cursor.execute(
                        "SELECT id FROM measurements WHERE plate_number = %s ORDER BY measured_at DESC LIMIT 1",
                        (plate_number,),
                    )
                    row = cursor.fetchone()
                    measurement_id = row[0] if row else None
                cursor.execute("""
                    INSERT INTO photos
                    (measurement_id, plate_number, photo_url, pathname, content_type, file_size)
                    VALUES (%s, %s, %s, %s, 'image/jpeg', %s)
                    RETURNING id, measurement_id, captured_at
                """, (measurement_id, plate_number, blob.url, blob.pathname, len(image_bytes)))
                photo_id, measurement_id, captured_at = cursor.fetchone()
    except (psycopg.Error, RuntimeError):
        app.logger.exception("Could not save capture metadata")
        return jsonify({"success": False, "error": "Photo stored, but metadata could not be saved"}), 500

    return jsonify({
        "success": True,
        "id": photo_id,
        "measurement_id": measurement_id,
        "plate_number": plate_number,
        "photo_url": blob.url,
        "captured_at": str(captured_at),
        "file_size": len(image_bytes),
        "detection": detection,
        **({"LDR_value": voltage, "unit": "V", "recognition_status": recognition_status} if is_capture else {}),
    }), 201

@app.route("/add", methods = ["POST"])
def add_measurement():

    plate_number = request.form["plate_number"]
    uv_value = float(request.form["uv_value"])

    try:
        insert_measurement(plate_number, uv_value)
    except (psycopg.Error, RuntimeError) as error:
        return f"Database error: {error}", 500

    return redirect("/")

@app.route("/api/measurements", methods=["GET"])
def api_get_measurements():
    try:
        measurements = fetch_measurements()
    except (psycopg.Error, RuntimeError) as error:
        return jsonify({
            "success": False,
            "error": str(error)
        }), 500

    return jsonify({
        "success": True,
        "measurements": [measurement_to_dict(row) for row in measurements]
    })


@app.route("/api/measurements", methods=["POST"])
def api_add_measurements():

    data = request.get_json(silent=True)

    if not data:
        return jsonify({
            "success" : False,
            "error": "No JSON data received"
        }), 400

    plate_number = data.get("plate_number")
    uv_value = data.get("uv_value")

    if not plate_number or uv_value is None:
        return jsonify({
            "success": False,
            "error": "plate_number and uv_value are required"
        }), 400

    try:
        uv_value = float(uv_value)
        limit_value = float(data.get("limit_value", DEFAULT_LIMIT_VALUE))
    except (TypeError, ValueError):
        return jsonify({
            "success": False,
            "error": "uv_value and limit_value must be numbers"
        }), 400

    unit = data.get("unit", DEFAULT_UNIT)

    try:
        measurement = insert_measurement(plate_number, uv_value, unit, limit_value)
    except (psycopg.Error, RuntimeError) as error:
        return jsonify({
            "success": False,
            "error": str(error)
        }), 500

    return jsonify({"success": True, **measurement}), 201


@app.route("/health")
def health():
    return jsonify({"success": True, "status": "ok"})


@app.route("/photos/<int:photo_id>")
def show_photo(photo_id):
    from vercel.blob.sync import get_blob
    from vercel.blob.errors import BlobNotFoundError

    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT pathname FROM photos WHERE id = %s",
                (photo_id,)
            )
            photo = cursor.fetchone()

    if photo is None:
        abort(404)

    try:
        result = get_blob(photo[0], access="private")
    except BlobNotFoundError:
        abort(404)
    except Exception:
        app.logger.exception("Could not read photo")
        return "Could not load photo", 502

    return Response(
        result.body,
        mimetype="image/jpeg",
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


if __name__ == "__main__":
    app.run(
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "false").lower() == "true"
    )
