#include <Servo.h>
#include <Wire.h>

const int NUM_SERVOS = 5;
Servo servos[NUM_SERVOS];
String line;

// ---------- OLED: write "REMOTE CONTROL" once, it stays on screen ----------
#define OLED_ADDR 0x3C
#define OLED_RST  4

const char GL_CH[] = "REMOTCNL ";
const uint8_t GL[][5] PROGMEM = {
  {0x7F,0x09,0x19,0x29,0x46}, // R
  {0x7F,0x49,0x49,0x49,0x41}, // E
  {0x7F,0x02,0x0C,0x02,0x7F}, // M
  {0x3E,0x41,0x41,0x41,0x3E}, // O
  {0x01,0x01,0x7F,0x01,0x01}, // T
  {0x3E,0x41,0x41,0x41,0x22}, // C
  {0x7F,0x04,0x08,0x10,0x7F}, // N
  {0x7F,0x40,0x40,0x40,0x40}, // L
  {0x00,0x00,0x00,0x00,0x00}, // space
};

void oCmd(uint8_t c) {
  Wire.beginTransmission(OLED_ADDR); Wire.write(0x00); Wire.write(c); Wire.endTransmission();
}
void oData(const uint8_t *d, uint8_t n) {
  Wire.beginTransmission(OLED_ADDR); Wire.write(0x40); Wire.write(d, n); Wire.endTransmission();
}
void oPos(uint8_t page, uint8_t col) {
  oCmd(0xB0 + page); oCmd(col & 0x0F); oCmd(0x10 | (col >> 4));
}

void oText2x(uint8_t page, uint8_t col, const char *s) {
  for (uint8_t half = 0; half < 2; half++) {
    oPos(page + half, col);
    for (const char *p = s; *p; p++) {
      const char *k = strchr(GL_CH, *p);
      uint8_t g = k ? (k - GL_CH) : 8;
      uint8_t out[12];
      for (uint8_t i = 0; i < 6; i++) {
        uint8_t b = (i < 5) ? pgm_read_byte(&GL[g][i]) : 0;
        uint8_t nib = half ? (b >> 4) : (b & 0x0F), e = 0;
        for (uint8_t j = 0; j < 4; j++) if (nib & (1 << j)) e |= 3 << (j * 2);
        out[i * 2] = e; out[i * 2 + 1] = e;
      }
      oData(out, 12);
    }
  }
}

void showRemoteControl() {
  pinMode(OLED_RST, OUTPUT);
  digitalWrite(OLED_RST, HIGH); delay(1);
  digitalWrite(OLED_RST, LOW);  delay(10);
  digitalWrite(OLED_RST, HIGH); delay(10);

  Wire.begin();
  Wire.setWireTimeout(3000, true);
  const uint8_t init[] = {0xAE,0xD5,0x80,0xA8,0x3F,0xD3,0x00,0x40,0x8D,0x14,
                          0x20,0x02,0xA1,0xC8,0xDA,0x12,0x81,0xCF,0xD9,0xF1,
                          0xDB,0x40,0xA4,0xA6};
  for (uint8_t i = 0; i < sizeof(init); i++) oCmd(init[i]);

  uint8_t zero[16] = {0};
  for (uint8_t pg = 0; pg < 8; pg++) { oPos(pg, 0); for (uint8_t i = 0; i < 8; i++) oData(zero, 16); }

  oText2x(1, 28, "REMOTE");
  oText2x(4, 22, "CONTROL");
  oCmd(0xAF);
  Wire.end();
}
// ---------------------------------------------------------------------------

String nextToken(const String &s, int &pos) {
  int end = s.indexOf(',', pos);
  int close = s.indexOf(']', pos);
  if (end == -1 || (close != -1 && close < end)) end = close;
  if (end == -1) end = s.length();
  String t = s.substring(pos, end);
  pos = end + 1;
  t.replace("'", "");
  t.replace("\"", "");
  t.trim();
  return t;
}

void handleLine(const String &s) {
  int pos = s.indexOf('[');
  if (pos == -1) return;
  pos++;
  String cmd = nextToken(s, pos);
  int a = nextToken(s, pos).toInt();
  int b = nextToken(s, pos).toInt();

  if (cmd == "setup") {
    Serial.println("succes");
  } else if (cmd == "servo_attach") {
    if (a >= 0 && a < NUM_SERVOS) servos[a].attach(b);
  } else if (cmd == "servo_write") {
    if (a >= 0 && a < NUM_SERVOS && servos[a].attached())
      servos[a].write(constrain(b, 0, 180));
  }
}

void setup() {
  Serial.begin(115200);
  line.reserve(64);
  showRemoteControl();
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      line.trim();
      if (line.length()) handleLine(line);
      line = "";
    } else if (line.length() < 120) {
      line += c;
    }
  }
}
