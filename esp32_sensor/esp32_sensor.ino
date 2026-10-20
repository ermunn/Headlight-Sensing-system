#include <WiFi.h>
#include <WiFiManager.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include "ybcam.h"

// -------------------- LDR CONFIGURATION --------------------
const int LDR_PIN = 34;
const float LDR_TRIGGER_VOLTAGE = 2.0f;
const float LDR_REARM_VOLTAGE = 1.9f;
const unsigned long LDR_SAMPLE_INTERVAL_MS = 100;

// -------------------- SERVER CONFIGURATION --------------------
// Flask API deployed on Vercel. It saves each measurement to the Neon database.
const char* SERVER_URL =
    "https://headlightsensingsystem.vercel.app/api/measurements";

// Configure this endpoint on your server to accept a raw image/jpeg POST.
const char* PHOTO_UPLOAD_URL =
    "https://headlightsensingsystem.vercel.app/api/photos";
// Set the same long random value as the Vercel PHOTO_UPLOAD_TOKEN environment variable.
const char* PHOTO_UPLOAD_TOKEN = "___PHOTO_UPLOAD_TOKEN___hjkiuoyugvbjn89y765476879809uiHJBHVGFYTGHUJBHMIIFVzCCAz+gAwIBAgINAgPlk28xsBNJiGuiFzANBgkqhkiG9w0BAQwFADBHMQswCQYDVQQGEwJVUzEiMCAGA1UEChMZR29vZ2xlIFRydXN0IFNlcnZpY2VzIExMQzEUMBIGA1UEAxMLR1RTIFJvb3QgUjEwHhcNMTYwNjIyMDAwMDAwWhcNMzYwNjIyMDAw";

// Root certificate used to verify the Vercel server over HTTPS
// (GTS Root R1, valid until 2036-06-22).
// If Vercel changes its certificate authority, requests fail with a
// negative HTTP code and this certificate must be replaced.
const char* ROOT_CA = R"EOF(
-----BEGIN CERTIFICATE-----
MIIFVzCCAz+gAwIBAgINAgPlk28xsBNJiGuiFzANBgkqhkiG9w0BAQwFADBHMQsw
CQYDVQQGEwJVUzEiMCAGA1UEChMZR29vZ2xlIFRydXN0IFNlcnZpY2VzIExMQzEU
MBIGA1UEAxMLR1RTIFJvb3QgUjEwHhcNMTYwNjIyMDAwMDAwWhcNMzYwNjIyMDAw
MDAwWjBHMQswCQYDVQQGEwJVUzEiMCAGA1UEChMZR29vZ2xlIFRydXN0IFNlcnZp
Y2VzIExMQzEUMBIGA1UEAxMLR1RTIFJvb3QgUjEwggIiMA0GCSqGSIb3DQEBAQUA
A4ICDwAwggIKAoICAQC2EQKLHuOhd5s73L+UPreVp0A8of2C+X0yBoJx9vaMf/vo
27xqLpeXo4xL+Sv2sfnOhB2x+cWX3u+58qPpvBKJXqeqUqv4IyfLpLGcY9vXmX7w
Cl7raKb0xlpHDU0QM+NOsROjyBhsS+z8CZDfnWQpJSMHobTSPS5g4M/SCYe7zUjw
TcLCeoiKu7rPWRnWr4+wB7CeMfGCwcDfLqZtbBkOtdh+JhpFAz2weaSUKK0Pfybl
qAj+lug8aJRT7oM6iCsVlgmy4HqMLnXWnOunVmSPlk9orj2XwoSPwLxAwAtcvfaH
szVsrBhQf4TgTM2S0yDpM7xSma8ytSmzJSq0SPly4cpk9+aCEI3oncKKiPo4Zor8
Y/kB+Xj9e1x3+naH+uzfsQ55lVe0vSbv1gHR6xYKu44LtcXFilWr06zqkUspzBmk
MiVOKvFlRNACzqrOSbTqn3yDsEB750Orp2yjj32JgfpMpf/VjsPOS+C12LOORc92
wO1AK/1TD7Cn1TsNsYqiA94xrcx36m97PtbfkSIS5r762DL8EGMUUXLeXdYWk70p
aDPvOmbsB4om3xPXV2V4J95eSRQAogB/mqghtqmxlbCluQ0WEdrHbEg8QOB+DVrN
VjzRlwW5y0vtOUucxD/SVRNuJLDWcfr0wbrM7Rv1/oFB2ACYPTrIrnqYNxgFlQID
AQABo0IwQDAOBgNVHQ8BAf8EBAMCAYYwDwYDVR0TAQH/BAUwAwEB/zAdBgNVHQ4E
FgQU5K8rJnEaK0gnhS9SZizv8IkTcT4wDQYJKoZIhvcNAQEMBQADggIBAJ+qQibb
C5u+/x6Wki4+omVKapi6Ist9wTrYggoGxval3sBOh2Z5ofmmWJyq+bXmYOfg6LEe
QkEzCzc9zolwFcq1JKjPa7XSQCGYzyI0zzvFIoTgxQ6KfF2I5DUkzps+GlQebtuy
h6f88/qBVRRiClmpIgUxPoLW7ttXNLwzldMXG+gnoot7TiYaelpkttGsN/H9oPM4
7HLwEXWdyzRSjeZ2axfG34arJ45JK3VmgRAhpuo+9K4l/3wV3s6MJT/KYnAK9y8J
ZgfIPxz88NtFMN9iiMG1D53Dn0reWVlHxYciNuaCp+0KueIHoI17eko8cdLiA6Ef
MgfdG+RCzgwARWGAtQsgWSl4vflVy2PFPEz0tv/bal8xa5meLMFrUKTX5hgUvYU/
Z6tGn6D/Qqc6f1zLXbBwHSs09dR2CQzreExZBfMzQsNhFRAbd03OIozUhfJFfbdT
6u9AWpQKXCBfTkBdYiJ23//OYb2MI3jSNwLgjt7RETeJ9r/tSQdirpLsQBqvFAnZ
0E6yove+7u7Y/9waLd64NnHi/Hm3lCXRSHNboTXns5lndcEZOitHTtNCjv0xyBZm
2tIMPNuzjsmhDYAPexZ3FL//2wmUspO8IFgV6dtxQ/PeEMMA3KgqlbbC1j+Qa3bb
bP6MvPJwNQzcmRk13NfIRmPVNnGuV/u3gm3c
-----END CERTIFICATE-----
)EOF";

// Temporary plate number for testing
const char* PLATE_NUMBER = "ESP32_TEST";

// Yahboom camera wiring: camera TX -> ESP32 GPIO16, camera RX -> GPIO17.
const int CAM_RX_PIN = 16;
const int CAM_TX_PIN = 17;
const uint32_t USB_SERIAL_BAUD = 115200;
const char* PHOTO_SIZE = "VGA";
const int PHOTO_QUALITY = 55;

WiFiManager wifiManager;

YbCam cam;
char commandLine[32];
size_t commandLength = 0;
uint32_t photoNumber = 0;
bool cameraReady = false;
bool ldrTriggerArmed = true;
unsigned long lastLdrSampleMs = 0;


// -------------------- WIFI SETUP --------------------
void connectWiFi() {
  WiFi.mode(WIFI_STA);

  // Time allowed to connect to a saved network
  wifiManager.setConnectTimeout(20);

  // Portal closes after 180 seconds
  wifiManager.setConfigPortalTimeout(180);

  Serial.println("Connecting to saved Wi-Fi...");

  if (!wifiManager.autoConnect("ESP32_Config")) {
    Serial.println("Wi-Fi setup failed. Restarting...");
    delay(1000);
    ESP.restart();
  }

  Serial.println("Wi-Fi connected!");
  Serial.print("SSID: ");
  Serial.println(WiFi.SSID());

  Serial.print("ESP32 IP: ");
  Serial.println(WiFi.localIP());
}


// -------------------- READ LDR --------------------
int readLDR() {
  return analogRead(LDR_PIN);
}


// -------------------- SEND DATA TO FLASK API (VERCEL) --------------------
bool sendMeasurement(int ldrValue, float voltage) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Wi-Fi disconnected. Cannot send data.");
    return false;
  }

  // HTTPS connection, verified against ROOT_CA
  WiFiClientSecure client;
  client.setCACert(ROOT_CA);

  HTTPClient http;

  if (!http.begin(client, SERVER_URL)) {
    Serial.println("ERROR could not initialize measurement request.");
    return false;
  }
  http.addHeader("Content-Type", "application/json");

  // HTTPS handshake plus a cold server start can take several seconds
  http.setConnectTimeout(10000);
  http.setTimeout(15000);

  // uv_value is currently used to store the LDR voltage.
  String jsonData = "{";
  jsonData += "\"plate_number\":\"";
  jsonData += PLATE_NUMBER;
  jsonData += "\",";
  jsonData += "\"uv_value\":";
  jsonData += String(voltage, 3);
  jsonData += "}";

  Serial.println("\nSending measurement...");
  Serial.print("LDR raw value: ");
  Serial.println(ldrValue);

  Serial.print("LDR voltage: ");
  Serial.println(voltage, 3);

  Serial.print("JSON: ");
  Serial.println(jsonData);

  int httpResponseCode = http.POST(jsonData);

  Serial.print("HTTP response code: ");
  Serial.println(httpResponseCode);

  if (httpResponseCode > 0) {
    String response = http.getString();

    Serial.println("Server response:");
    Serial.println(response);
  } else {
    Serial.print("HTTP error: ");
    Serial.println(http.errorToString(httpResponseCode));
  }

  http.end();
  return httpResponseCode >= 200 && httpResponseCode < 300;
}


// -------------------- CAPTURE AND UPLOAD PHOTO --------------------
void sendPhotoAndMeasurement(int ldrValue, float voltage) {
  if (!cameraReady) {
    Serial.println("ERROR camera is not ready; check camera wiring and power.");
    return;
  }
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("ERROR Wi-Fi is disconnected; photo not uploaded.");
    return;
  }

  Serial.println("Taking photo...");
  if (!cam.takePhoto(PHOTO_SIZE, PHOTO_QUALITY, 20000)) {
    Serial.print("ERROR camera: ");
    Serial.println(cam.text());
    return;
  }

  const YbFrame &frame = cam.frame();
  if (!frame.data || frame.len < 4 || frame.data[0] != 0xFF ||
      frame.data[1] != 0xD8 || frame.data[frame.len - 2] != 0xFF ||
      frame.data[frame.len - 1] != 0xD9) {
    Serial.println("ERROR camera returned an invalid JPEG.");
    return;
  }

  // Save the reading that triggered capture so the photo links to that event.
  if (!sendMeasurement(ldrValue, voltage)) {
    Serial.println("ERROR measurement failed; photo upload cancelled. Waiting for next threshold crossing.");
    return;
  }

  WiFiClientSecure client;
  client.setCACert(ROOT_CA);
  HTTPClient http;
  http.setConnectTimeout(15000);
  http.setTimeout(30000);

  if (!http.begin(client, PHOTO_UPLOAD_URL)) {
    Serial.println("ERROR could not initialize photo upload request.");
    return;
  }

  http.addHeader("Content-Type", "image/jpeg");
  http.addHeader("X-Plate-Number", PLATE_NUMBER);
  http.addHeader("X-Photo-Number", String(photoNumber + 1));
  http.addHeader("X-Upload-Token", PHOTO_UPLOAD_TOKEN);
  Serial.printf("Uploading JPEG (%lu bytes)...\n", (unsigned long)frame.len);
  int status = http.POST(frame.data, frame.len);
  Serial.printf("Photo upload HTTP status: %d\n", status);
  if (status > 0) {
    Serial.println(http.getString());
    if (status >= 200 && status < 300) {
      ++photoNumber;
      Serial.println("DONE measurement and photo sent.");
    } else {
      Serial.println("ERROR measurement saved, but photo upload failed.");
    }
  } else {
    Serial.print("Upload error: ");
    Serial.println(http.errorToString(status));
    Serial.println("ERROR measurement saved, but photo upload failed.");
  }
  http.end();
}


// Read newline-terminated commands from the USB serial monitor.
void processSerialCommands() {
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (commandLength == 0) continue;
      commandLine[commandLength] = '\0';
      if (!strcmp(commandLine, "help")) {
        Serial.println("Automatic capture above 2.0 V; rearmed at or below 1.9 V. Commands: help");
      } else {
        Serial.print("Unknown command: ");
        Serial.println(commandLine);
        Serial.println("Type help for commands.");
      }
      commandLength = 0;
    } else if (commandLength < sizeof(commandLine) - 1) {
      commandLine[commandLength++] = c;
    } else {
      commandLength = 0;
      Serial.println("ERROR command too long.");
    }
  }
}


// -------------------- SETUP --------------------
void setup() {
  Serial.begin(USB_SERIAL_BAUD);
  delay(500);

  analogReadResolution(12);
  pinMode(LDR_PIN, INPUT);

  Serial.println("\nESP32 LDR Monitoring System");

  connectWiFi();

  if (!cam.begin(CAM_RX_PIN, CAM_TX_PIN)) {
    Serial.println("ERROR camera buffer allocation failed.");
  } else if (!cam.command("INFO", 5000)) {
    Serial.print("ERROR camera link: ");
    Serial.println(cam.text());
  } else {
    cameraReady = true;
    Serial.println("Yahboom camera ready.");
  }

  Serial.println("System ready. Automatic photo and measurement above 2.0 V; rearmed at or below 1.9 V.");
}


// -------------------- MAIN LOOP --------------------
void loop() {
  processSerialCommands();

  // Attempt to reconnect if Wi-Fi drops
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Wi-Fi disconnected. Reconnecting...");
    WiFi.reconnect();
    delay(1000);
  }

  unsigned long now = millis();
  if (now - lastLdrSampleMs < LDR_SAMPLE_INTERVAL_MS) return;
  lastLdrSampleMs = now;

  int ldrValue = readLDR();
  float voltage = ldrValue * (3.3f / 4095.0f);
  if (!ldrTriggerArmed) {
    if (voltage <= LDR_REARM_VOLTAGE) {
      ldrTriggerArmed = true;
      Serial.println("LDR at or below 1.9 V; ready for next capture.");
    }
    return;
  }

  if (voltage > LDR_TRIGGER_VOLTAGE && cameraReady &&
      WiFi.status() == WL_CONNECTED) {
    // Latch before blocking camera/HTTP work to prevent repeated uploads.
    ldrTriggerArmed = false;
    Serial.printf("LDR threshold exceeded: %.3f V.\n", voltage);
    sendPhotoAndMeasurement(ldrValue, voltage);
  }
}
