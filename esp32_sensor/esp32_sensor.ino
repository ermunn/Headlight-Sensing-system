#include <WiFi.h>
#include <WiFiManager.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>

// -------------------- LDR CONFIGURATION --------------------
const int LDR_PIN = 4;

// -------------------- SERVER CONFIGURATION --------------------
// Flask API deployed on Vercel. It saves each measurement to the Neon database.
const char* SERVER_URL =
    "https://headlight-sensing-system.vercel.app/api/measurements";

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

// Send data every 5 seconds
const unsigned long SEND_INTERVAL = 5000;

WiFiManager wifiManager;

unsigned long previousSendTime = 0;


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
void sendMeasurement(int ldrValue, float voltage) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Wi-Fi disconnected. Cannot send data.");
    return;
  }

  // HTTPS connection, verified against ROOT_CA
  WiFiClientSecure client;
  client.setCACert(ROOT_CA);

  HTTPClient http;

  http.begin(client, SERVER_URL);
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
}


// -------------------- SETUP --------------------
void setup() {
  Serial.begin(115200);
  delay(500);

  analogReadResolution(12);

  Serial.println("\nESP32 LDR Monitoring System");

  connectWiFi();

  Serial.println("System ready!");
}


// -------------------- MAIN LOOP --------------------
void loop() {
  unsigned long currentTime = millis();

  if (currentTime - previousSendTime >= SEND_INTERVAL) {
    previousSendTime = currentTime;

    // Read sensor
    int ldrValue = readLDR();

    // Approximate voltage for a 3.3 V ADC range
    float voltage = ldrValue * (3.3f / 4095.0f);

    // Send measurement to Flask API
    sendMeasurement(ldrValue, voltage);
  }

  // Attempt to reconnect if Wi-Fi drops
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Wi-Fi disconnected. Reconnecting...");
    WiFi.reconnect();
    delay(1000);
  }
}
