from flask import Flask, render_template, request, redirect, jsonify
import mariadb

app = Flask(__name__)

def get_db_connection():
	return mariadb.connect(
		host = "localhost",
		user = "HL_admin",
		password = "teee123456",
		database = "headlight_system"
	)

@app.route("/")
def home():

	conn = get_db_connection()
	cursor = conn.cursor()

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

	measurements = cursor.fetchall()

	cursor.close()
	conn.close()

	return render_template(
		"index.html",
		measurements = measurements
	)

@app.route("/add", methods = ["POST"])
def add_measurement():

	plate_number = request.form["plate_number"]
	uv_value = request.form["uv_value"]
	unit = request.form["unit"]
	limit_value = request.form["limit_value"]

	if float(uv_value) > float(limit_value):
		status = "fail"
	else:
		status = "Pass"

	conn = get_db_connection()
	cursor = conn.cursor()

	cursor.execute("""
		INSERT INTO measurements
		(plate_number, measured_at, uv_value, unit, limit_value, status)
		VALUES (?, NOW(), ?, ?, ?, ?)
	     """,(
		plate_number,
		uv_value,
		unit,
		limit_value,
		status
		))

	conn.commit()

	cursor.close()
	conn.close()

	return redirect("/")

@app.route("/api/measurements", methods=["POST"])
def api_add_measurements():

	data = request .get_json()

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
			"error": "No JSON data received"
		}), 400

	try:
		uv_value = float(uv_value)
	except ValueError:
		return jsonify({
			"success": False,
			"error": "uv_value must be a number"
		}), 400

	unit = "mW/cm^2"
	limit_value = 1.000

	if uv_value > limit_value:
		status = "Fail"
	else:
		status = "Pass"

	conn = get_db_connection()
	cursor = conn.cursor()

	cursor.execute("""
		INSERT INTO measurements
		(plate_number, measured_at, uv_value, unit, limit_value, status)
		Values(?, NOW(), ?, ?, ?, ?)
	     """, (
		plate_number,
		uv_value, 
		unit, 
		limit_value, 
		status
	))

	conn.commit()

	measurement_id = cursor.lastrowid

	cursor.close()
	conn.close()

	return jsonify({
		"success": True,
		"id": measurement_id,
		"plate_number": plate_number,
		"uv_value": uv_value,
		"unit": unit,
		"limit_value": limit_value,
		"status": status
	}), 201


if __name__ == "__main__":
	app.run(
		host = "0.0.0.0",
		port = 5000,
		debug = True
	)
