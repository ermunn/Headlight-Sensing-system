# Headlight Sensing System

ESP32-д суурилсан гэрлийн хэмжилт, автомашины зураг болон улсын дугаарын
мэдээлэл бүртгэх систем. Backend нь Flask, өгөгдлийн сан нь Neon PostgreSQL,
зураг хадгалалт нь private Vercel Blob ашиглана.

## Одоогийн ажиллагаа

- ESP32 LDR voltage хэмжиж, 2.0 V-оос давахад UART камерын JPEG зураг илгээнэ.
  1.9 V буюу түүнээс доош болоход дараагийн capture-д бэлэн болно.
- Roboflow Workflow дугаарын байрлалыг илрүүлнэ.
- Plate Recognizer тохируулсан үед дугаарын текст уншина.
- Web хүснэгтэд дугаар, хэмжилт, Pass/Fail, зураг, UTC+8 цаг харагдана.

LDR voltage нь calibrated гэрлийн эрчим эсвэл хуульд нийцлийн баталгаа биш.
Түүхэн `uv_value` database column одоо capture-ийн voltage-ийг `V` нэгжтэй хадгалдаг.

## Бүтэц

```text
app.py                       Flask routes, database, OCR
roboflow_workflow.py          Hosted Workflow HTTP client
roboflow_workflow.json        MCP-ээр баталгаажуулсан Workflow contract
schema.sql                   Database schema
templates/                   Web HTML
static/                      Web CSS
esp32_sensor/                Firmware, UART camera driver, secrets template
tests/                       Unit tests, opt-in smoke test, response fixture
scripts/check_db.py           Database connection diagnostic
docs/CAPTURE_SETUP.md         Capture API, firmware, Roboflow setup
requirements.txt             Runtime dependencies
vercel.json                  Vercel configuration
```

## Local setup

Python 3.12 ашиглана (`.python-version`). Repository root дотроос PowerShell-д:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

`.env` файлд өөрийн утгуудыг тохируулна:

| Variable | Зориулалт |
| --- | --- |
| `DATABASE_URL` | PostgreSQL connection string |
| `BLOB_READ_WRITE_TOKEN` | Private Vercel Blob access |
| `PHOTO_UPLOAD_TOKEN` | ESP32 болон backend-ийн ижил upload token |
| `ROBOFLOW_API_KEY` | Optional plate detection |
| `PLATE_RECOGNIZER_TOKEN` | Optional plate text OCR |

Neon SQL Editor эсвэл өөр PostgreSQL client ашиглан `schema.sql`-ийг ажиллуулна.
Энэ нь `CREATE TABLE IF NOT EXISTS` schema бөгөөд migration system биш.

```powershell
python app.py
```

Web: https://headlightsensingsystem.vercel.app/ — health check: https://headlightsensingsystem.vercel.app/health .
Бодит зураг upload хийхэд Blob token болон database шаардлагатай.

## Firmware ба deployment

Firmware-ийн `PHOTO_UPLOAD_URL`-ийг өөрийн backend endpoint-д тохируулна.
`esp32_sensor/secrets.example.h`-ийг `secrets.h` болгон хуулж, upload token-оо
оруулна. Arduino IDE-д ESP32 board support болон WiFiManager шаардлагатай.
Камер нь `ybcam.h`-ийн UART protocol-той нийцсэн firmware ашиглах ёстой;
камерын тусдаа firmware энэ repository-д байхгүй.

Vercel-д дээрх environment variables-ийг тохируулж deploy хийнэ.
Dependency өөрчилсөн бол build cache-гүй redeploy хийж bundle size-ийг шалгана.
Backend нь hosted inference ашигладаг тул `inference-sdk`, OpenCV зэрэг local
vision dependencies runtime requirements-д нэмэхгүй.

Дэлгэрэнгүй: [Capture setup](docs/CAPTURE_SETUP.md).

## Шалгалт

```powershell
python -m unittest discover -s tests -v
```

Unit tests нь database, Blob, inference services-ийг mock ашиглан шалгана.
Live smoke test default-оор алгасагдана; ажиллуулах заавар нь capture setup-д бий.

## Хамтран хөгжүүлэх ба license

[CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md)-ийг уншина уу.
Төсөл [MIT License](LICENSE)-тэй. External services, models, dependencies-ийн
өөрсдийн нөхцөл хэвээр үйлчилнэ; license нь API access эрх олгохгүй.
