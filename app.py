import os

from flask import Flask, render_template, request, redirect, jsonify
import psycopg

app = Flask(__name__)

DEFAULT_UNIT = "mW/cm^2"
DEFAULT_LIMIT_VALUE = 1.000


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
			SELECT plate_number,
			       measured_at,
			       uv_value,
			       unit,
			       limit_value,
			       status
			FROM measurements
			ORDER BY measured_at DESC
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


@app.route("/")
def home():
	try:
		measurements = fetch_measurements()
	except (psycopg.Error, RuntimeError) as error:
		return f"Database error: {error}", 500

	return render_template("index.html", measurements=measurements)

@app.route("/add", methods = ["POST"])
def add_measurement():

	plate_number = request.form["plate_number"]
	uv_value = float(request.form["uv_value"])
	unit = request.form["unit"]
	limit_value = float(request.form["limit_value"])

	try:
		insert_measurement(plate_number, uv_value, unit, limit_value)
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


if __name__ == "__main__":
	app.run(
		host=os.getenv("HOST", "0.0.0.0"),
		port=int(os.getenv("PORT", "5000")),
		debug=os.getenv("FLASK_DEBUG", "false").lower() == "true"
	)
