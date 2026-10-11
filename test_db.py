import mariadb

try:
	conn = mariadb.connect(
		host = "localhost",
		user = "HL_admin",
		password = "teee123456",
		database = "headlight_system"
	)

	print("Successfully connected to MariaDB!")

	cursor = conn.cursor()
	cursor.execute("SHOW TABLES")

	print("Tables:")
	for table in cursor:
		print(table)

	cursor.close()
	conn.close()

except mariadb.Error as e:
	print(f"Error connecting to MariaDB: {e}")
