/* ============================================================================
   ybcam.h — Yahboom UART камерын драйвер (удирдагч ESP32 тал)
   ----------------------------------------------------------------------------
   Yahboom дээр `yahboom-cam` firmware суусан байх ёстой (yahboom-cam/yahboom-cam.ino —
   протоколын тайлбар тэнд). Энэ файл өөр юунаас ч хамаарахгүй: өөр project руу тэр
   чигээр нь хуулж `#include "ybcam.h"` хийхэд хангалттай.

     YbCam cam;
     cam.begin(16, 17);                          // RX ← Yahboom TX · TX → Yahboom RX

     if (cam.takePhoto())                        // ── зураг авах ──
       use(cam.frame().data, cam.frame().len);   //    JPEG

     cam.recStart();                             // ── бичлэг эхлэх ──
     if (cam.poll() == 'V')                      //    loop() дотор: кадр бүр
       use(cam.frame().data, cam.frame().len);   //    JPEG
     cam.recStop();                              // ── бичлэг зогсох ──

   Хариу бүрийн текст (`OK …` / `ERR …`) нь cam.text()-д үлдэнэ.
   ============================================================================ */
#pragma once
#include <Arduino.h>
#include <stdarg.h>

struct YbFrame {
  char     type;   /* 'P' зураг · 'V' бичлэгийн кадр · 0 = хүчингүй */
  uint8_t  seq;    /* 'V': кадрын дугаар 0..255 (эргэнэ) */
  uint32_t len;    /* JPEG-ийн урт, байт */
  uint8_t *data;   /* JPEG (FF D8 … FF D9). Дараагийн 'P'/'V' фрейм ирэхэд ДАРАГДАНА */
};

/* CRC-32 (zlib.crc32-тай ижил): эхлэх утга 0xFFFFFFFF, эцэст нь ~ хийнэ. Залгаж тооцож болно. */
static inline uint32_t ybCrc(uint32_t c, const uint8_t *p, size_t n) {
  while (n--) { c ^= *p++; for (int k = 0; k < 8; k++) c = (c >> 1) ^ (0xEDB88320u & (0u - (c & 1))); }
  return c;
}

class YbCam {
 public:
  /* frames / bytes = хүлээн авсан 'V' кадр. Алдаанууд эрүүл линк дээр 0 байна:
     crcErr = гэмтсэн фрейм · lenErr = буферт багтаагүй / утгагүй урт · gapErr = дундуураа
     тасарсан · seqGap = бүхлээрээ алга болсон кадр. */
  uint32_t frames = 0, bytes = 0, crcErr = 0, lenErr = 0, gapErr = 0, seqGap = 0;

  /* cap = JPEG хүлээн авах буфер (байт). Зураг үүнээс том гарвал Yahboom чанарыг бууруулж
     багтаана. Энгийн ESP32 (PSRAM-гүй)-д 64 КБ тохиромжтой; WiFi асаавал багасгаж болно. */
  bool begin(int rxPin = 16, int txPin = 17, size_t cap = 64 * 1024, uint32_t baud = 1000000,
             HardwareSerial &port = Serial2) {
    _port = &port; _cap = cap;
    _buf = (uint8_t *)malloc(cap);
    if (!_buf) return false;
    _f = { 0, 0, 0, _buf };
    port.setRxBufferSize(16384);               /* begin()-ээс ӨМНӨ. 1 Мбод дээр ≈160 мс-ийн нөөц */
    port.begin(baud, SERIAL_8N1, rxPin, txPin);
    port.setRxFIFOFull(64);                    /* 128 байтын FIFO-д 640 мкс нөөц үлдээнэ */
    return true;
  }

  /* Yahboom-ыг RESET товчны падаар (EN) дахин ачаалж `READY …` иртэл хүлээнэ.
     Нээлттэй сток: LOW татна, эс бол Hi-Z — HIGH руу хэзээ ч жолоодохгүй. */
  bool reset(int enPin, uint32_t timeoutMs = 6000) {
    pinMode(enPin, OUTPUT); digitalWrite(enPin, LOW);
    delay(120);
    pinMode(enPin, INPUT);
    _st = HUNT; _w = 0;
    return waitText("READY", timeoutMs);
  }

  /* Түүхий команд (хариуг хүлээхгүй). Жишээ: send("REC 0") */
  void send(const char *line) { _port->print(line); _port->print('\n'); }
  void sendf(const char *fmt, ...) {
    char b[96];
    va_list ap; va_start(ap, fmt); vsnprintf(b, sizeof(b), fmt, ap); va_end(ap);
    send(b);
  }

  /* Команд илгээж текст хариуг хүлээнэ: `OK…`/`INFO…` → true, `ERR…`/хариугүй → false.
     Хариу нь text()-д. Жишээ: command("INFO") · command("SET vflip 0") */
  bool command(const char *line, uint32_t timeoutMs = 3000) {
    send(line);
    return waitText(nullptr, timeoutMs);
  }

  /* ── ЗУРАГ АВАХ ── амжилттай бол frame() = JPEG, text() = "OK PHOTO SVGA 800x600 q=70 len=… ms=…".
     size: "QVGA" 320x240 · "VGA" 640x480 · "SVGA" 800x600 · "XGA" 1024x768.  quality: 5..95.
     Хэмжээ солигдох үед камер дахин асдаг тул эхний зураг ≈2.5–3.5 с, дараагийнх ≈1–1.5 с. */
  bool takePhoto(const char *size = "SVGA", int quality = 70, uint32_t timeoutMs = 15000) {
    sendf("PHOTO %s %d %u", size, quality, (unsigned)_cap);
    const uint32_t t0 = millis();
    while (millis() - t0 < timeoutMs) {
      const char t = poll();
      if (t == 'P') { waitText("OK PHOTO", 800); return true; }      /* араас нь ирэх тайлбар мөр */
      if (t == 'T' && !strncmp(_text, "ERR", 3)) return false;
      if (!t) delay(1);
    }
    strlcpy(_text, "ERR PHOTO timeout (no reply from camera)", sizeof(_text));
    return false;
  }

  /* ── БИЧЛЭГ ── recStart()-ийн дараа кадрууд тасралтгүй ирнэ: loop() дотор poll() == 'V'.
     QVGA ≈11–12 fps (кадр 3–6 КБ) · VGA ≈2.4 fps (кадр ≈10 КБ). */
  bool recStart(const char *size = "QVGA", int quality = 40, uint32_t timeoutMs = 6000) {
    frames = bytes = seqGap = 0; _haveSeq = false;
    sendf("REC 1 %s %d", size, quality);
    return waitText("OK REC 1", timeoutMs);
  }
  /* Зогсоож `OK REC 0 frames=… bytes=… ms=… dropped=…` хариуг хүлээнэ. ⚠ Хүлээх зуур ирсэн
     сүүлийн кадрууд хаягдана — тэднийг ч авах бол send("REC 0") хийгээд poll()-оо үргэлжлүүл. */
  bool recStop(uint32_t timeoutMs = 4000) {
    send("REC 0");
    return waitText("OK REC 0", timeoutMs);
  }

  /* Ирсэн байтыг задална. Бүтэн фрейм гүйцмэгц төрлийг нь буцаана:
       'P' / 'V' → frame() шинэчлэгдлээ · 'T' → text() шинэчлэгдлээ · 0 → одоохондоо юу ч алга.
     Блоклохгүй — loop() дотор байнга дуудна. */
  char poll() {
    for (;;) {
      if (_ti >= _tn) {
        const int a = _port->available();
        if (a <= 0) break;
        _tn = (int)_port->read(_tmp, a > (int)sizeof(_tmp) ? sizeof(_tmp) : (size_t)a);
        _ti = 0;
        if (_tn <= 0) { _tn = 0; break; }
        _lastRx = millis();
      }
      while (_ti < _tn) {
        switch (_st) {
          case HUNT:                                   /* magic 'Y' 'B' A5 5A хайна; бусдыг хаяна */
            _w = (_w << 8) | _tmp[_ti++];
            if (_w == 0x5942A55Au) { _n = 0; _st = HDR; }
            break;
          case HDR:                                    /* type · seq · len u32 LE */
            _h[_n++] = _tmp[_ti++];
            if (_n == 6) {
              _len = (uint32_t)_h[2] | ((uint32_t)_h[3] << 8) | ((uint32_t)_h[4] << 16) | ((uint32_t)_h[5] << 24);
              if (_len > 1048576u) { lenErr++; _st = HUNT; _w = 0; break; }      /* утгагүй урт */
              const bool isText = (_h[0] == 'T');
              _dst = isText ? (uint8_t *)_text : _buf;
              _dcap = isText ? sizeof(_text) - 1 : _cap;
              if (!isText) _f.type = 0;                /* буфер дарагдах гэж байна */
              _crc = ybCrc(0xFFFFFFFFu, _h, 6);
              _got = 0; _n = 0; _st = _len ? PAY : CRC;
            }
            break;
          case PAY: {
            size_t take = _len - _got;
            if (take > (size_t)(_tn - _ti)) take = (size_t)(_tn - _ti);
            if (_got < _dcap) memcpy(_dst + _got, _tmp + _ti, take > _dcap - _got ? _dcap - _got : take);
            _crc = ybCrc(_crc, _tmp + _ti, take);
            _got += take; _ti += (int)take;
            if (_got == _len) _st = CRC;
            break;
          }
          case CRC:
            _c[_n++] = _tmp[_ti++];
            if (_n == 4) {
              _st = HUNT; _w = 0;
              const uint32_t want = (uint32_t)_c[0] | ((uint32_t)_c[1] << 8) | ((uint32_t)_c[2] << 16) | ((uint32_t)_c[3] << 24);
              const char type = (char)_h[0];
              if (want != ~_crc) { crcErr++; if (type == 'T') _text[0] = 0; break; }
              if (type == 'T') { _text[_len < sizeof(_text) - 1 ? _len : sizeof(_text) - 1] = 0; return 'T'; }
              if (_len > _cap) {                       /* буферт багтаагүй — cap-ыг томруул */
                lenErr++;
                snprintf(_text, sizeof(_text), "ERR frame %lu bytes > buffer %u", (unsigned long)_len, (unsigned)_cap);
                return 'T';
              }
              _f = { type, _h[1], _len, _buf };
              if (type == 'V') {
                if (_haveSeq && (uint8_t)(_f.seq - _lastSeq) != 1) seqGap++;
                _lastSeq = _f.seq; _haveSeq = true;
                frames++; bytes += _len;
              }
              return type;
            }
            break;
        }
      }
    }
    if (_st != HUNT && millis() - _lastRx > 500) { gapErr++; _st = HUNT; _w = 0; }   /* дундуураа тасарсан */
    return 0;
  }

  const YbFrame &frame() const { return _f; }      /* сүүлийн 'P' / 'V' */
  const char *text() const { return _text; }       /* сүүлийн текст хариу */
  size_t capacity() const { return _cap; }

  /* `prefix`-ээр эхэлсэн текст иртэл хүлээнэ (prefix = nullptr бол дурын текст).
     `ERR…` ирвэл эсвэл хугацаа дуусвал false. Хүлээх зуур ирсэн 'P'/'V' фрейм алгасагдана. */
  bool waitText(const char *prefix, uint32_t timeoutMs) {
    const uint32_t t0 = millis();
    while (millis() - t0 < timeoutMs) {
      const char t = poll();
      if (t == 'T') {
        if (!strncmp(_text, "ERR", 3)) return false;
        if (!prefix || !strncmp(_text, prefix, strlen(prefix))) return true;
      } else if (!t) delay(1);
    }
    strlcpy(_text, "ERR timeout (no reply from camera)", sizeof(_text));
    return false;
  }

 private:
  enum : uint8_t { HUNT, HDR, PAY, CRC };
  HardwareSerial *_port = nullptr;
  uint8_t *_buf = nullptr, *_dst = nullptr;
  size_t   _cap = 0, _dcap = 0;
  YbFrame  _f = { 0, 0, 0, nullptr };
  char     _text[200] = "";
  uint8_t  _tmp[512], _h[6], _c[4], _st = HUNT, _n = 0, _lastSeq = 0;
  int      _ti = 0, _tn = 0;
  bool     _haveSeq = false;
  uint32_t _w = 0, _len = 0, _got = 0, _crc = 0, _lastRx = 0;
};
