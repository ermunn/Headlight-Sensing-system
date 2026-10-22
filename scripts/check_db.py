import os
from pathlib import Path

from dotenv import load_dotenv


def main():
	import psycopg

	load_dotenv(Path(__file__).resolve().parents[1] / ".env")

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

	except (psycopg.Error, RuntimeError):
		print("Database check failed. Verify DATABASE_URL and network access.")


if __name__ == "__main__":
	main()
