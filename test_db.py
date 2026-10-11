import os


def main():
	import psycopg

	try:
		database_url = os.getenv("DATABASE_URL")
		if not database_url:
			raise RuntimeError("DATABASE_URL environment variable is not set")

		conn = psycopg.connect(database_url)

		print("Successfully connected to Neon Postgres!")

		cursor = conn.cursor()
		cursor.execute("""
			SELECT table_name
			FROM information_schema.tables
			WHERE table_schema = 'public'
			ORDER BY table_name
		""")

		print("Tables:")
		for table in cursor:
			print(table)

		cursor.close()
		conn.close()

	except (psycopg.Error, RuntimeError) as e:
		print(f"Error connecting to Neon Postgres: {e}")


if __name__ == "__main__":
	main()
