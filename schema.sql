CREATE TABLE IF NOT EXISTS measurements (
	id SERIAL PRIMARY KEY,
	plate_number TEXT NOT NULL,
	measured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
	uv_value DOUBLE PRECISION NOT NULL,
	unit TEXT NOT NULL,
	limit_value DOUBLE PRECISION NOT NULL,
	status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS photos (
	id SERIAL PRIMARY KEY,
	measurement_id INTEGER REFERENCES measurements(id) ON DELETE SET NULL,
	plate_number TEXT NOT NULL,
	photo_url TEXT NOT NULL,
	pathname TEXT NOT NULL,
	captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
	content_type TEXT NOT NULL DEFAULT 'image/jpeg',
	file_size INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS photos_measurement_id_captured_at_idx
	ON photos (measurement_id, captured_at DESC);
