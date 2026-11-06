#include <Arduino.h>
#include <AccelStepper.h>
#include <DallasTemperature.h>
#include <OneWire.h>
#include <Wire.h>
#include <Adafruit_INA219.h>

// Definicje pinów
#define MotorDirPin 27 
#define MotorStepPin 14 
#define MotorSleepPin 5 
#define MosfetGatePin 25
#define FanPin 26 
#define OneWireBus 4 
#define LimitZeroPin 12 
#define LimitMaxPin 13


// Inicjalizacja obiektów
AccelStepper stepper(AccelStepper::DRIVER, MotorStepPin, MotorDirPin);
OneWire oneWire(OneWireBus);
DallasTemperature sensors(&oneWire);
Adafruit_INA219 ina219;

// Zmienne do sterowania kątem obrotu
float targetAngle = 0.0f;

int pwmValue = 0;
bool shutdownRequested = false;

// Zmienne do pomiaru charakterystyki I-U
bool inSweepingProcess = false;
float lastSentV = 100.0f;
float lastSentI = -100.0f; 

// Zmienne do algorytmu MPPT
bool inMpptProcess = false;
int mpptStep = 50;  
float mpptPowerTolerance = 0.001f;
int mpptDirection = 1; // 1 = zwiększanie PWM, -1 = zmniejszanie PWM
float previousMpptPower = 0.0f;
bool hasPreviousMpptPower = false;

// Zmienne do chłodzenia
float targetTemp = 100.0f;

// Zmienne dla regulatora PI
float Kp = 400.0f;  
float Ki = 1.5f;     
float integral = 0.0f;

// ====================== SETUP ======================
void setup() {
  Serial.begin(115200);
  Serial.println("Rozpoczynam setup...");
  sensors.begin();
  
  if (!ina219.begin()) {
    Serial.println("Nie znaleziono INA219!");
  }

  // Inicjalizacja PWM MOSFET (Kanał 0, 5000 Hz, 12-bit)
  ledcSetup(0, 5000, 12); 
  ledcAttachPin(MosfetGatePin, 0);
  ledcWrite(0, 0); 

  // Inicjalizacja PWM Wiatraka (Kanał 2, 5000 Hz, 8-bit)
  ledcSetup(2, 5000, 8); 
  ledcAttachPin(FanPin, 2);
  ledcWrite(2, 0);

  // Ustawienie pinu SLEEP sterownika DRV8825 jako wyjście i ustawienie go w stan wysoki
  pinMode(MotorSleepPin, OUTPUT);
  digitalWrite(MotorSleepPin, HIGH);

  // Ustawienie pinów krańcówek jako wejścia z podciąganiem
  pinMode(LimitZeroPin, INPUT_PULLUP);
  pinMode(LimitMaxPin, INPUT_PULLUP);

  // ====================== BAZOWANIE ======================
  stepper.setPinsInverted(true, false, false);
  stepper.setMaxSpeed(400.0);
  stepper.setAcceleration(200.0);
  stepper.setSpeed(-50.0); 

  Serial.println("Rozpoczynam bazowanie...");
  while (digitalRead(LimitZeroPin) == HIGH) {
      stepper.runSpeed(); 
      yield();
  }
  stepper.setCurrentPosition(0);
  stepper.moveTo(0);
  Serial.println("Bazowanie zakończone.");
  Serial.println("Setup zakończony.");
}

void loop() {

  // =============== OBSŁUGA KOMEND Z PORTU SZEREGOWEGO ======================
  if (Serial.available() > 0) {
    String input = Serial.readStringUntil('\n');
    input.trim(); 

    if (input == "SWEEP") {
      shutdownRequested = false;
      inMpptProcess = false;
      inSweepingProcess = true;
      pwmValue = 0;
      lastSentV = 100.0f; 
      lastSentI = -100.0f;
      ledcWrite(0, 0);
      
      // Zamrożenie pozycji silnika krokowego
      stepper.moveTo(stepper.currentPosition()); 
      
      delay(300); 
      Serial.println("{\"mode\":\"sweep_start\"}");
    } 
    else if (input == "ABORT") {
      inSweepingProcess = false;
      inMpptProcess = false;
      pwmValue = 0;
      ledcWrite(0, 0); 
      Serial.println("{\"mode\":\"sweep_aborted\"}");
    }
    else if (input == "MPPT_START") {
      shutdownRequested = false;
      inSweepingProcess = false;
      inMpptProcess = true;
      pwmValue = 0;
      mpptDirection = 1;
      previousMpptPower = 0.0f;
      hasPreviousMpptPower = false;
      ledcWrite(0, 0);
      Serial.println("{\"mode\":\"mppt_started\"}");
    }
    else if (input == "MPPT_STOP") {
      inMpptProcess = false;
      pwmValue = 0;
      ledcWrite(0, 0);
      Serial.println("{\"mode\":\"mppt_stopped\"}");
    }
    else if (input.startsWith("ANGLE:")) {
        shutdownRequested = false;
        targetAngle = input.substring(6).toFloat();
        float targetSteps = round(targetAngle / 1.8f);
        stepper.moveTo(targetSteps);
    }
    else if (input.startsWith("TEMP:")) {
        shutdownRequested = false;
        targetTemp = input.substring(5).toFloat();
    }
    else if (input == "WAKE") {
      shutdownRequested = false;
      Serial.println("{\"mode\":\"wake\"}");
    }
    else if (input == "SHUTDOWN") {
      inSweepingProcess = false;
      inMpptProcess = false;
      shutdownRequested = true;
      pwmValue = 0;
      ledcWrite(0, 0);
      ledcWrite(2, 0);
      stepper.moveTo(stepper.currentPosition());
      Serial.println("{\"mode\":\"shutdown\"}");
    }
  }

  // ================= ZABEZPIECZENIA KRAŃCOWE =================
  // ZABEZPIECZENIE 90 STOPNI
  if (digitalRead(LimitMaxPin) == LOW && stepper.distanceToGo() > 0) {
      stepper.setCurrentPosition(50);
      stepper.moveTo(50);
  }
  
  // ZABEZPIECZENIE 0 STOPNI
  if (digitalRead(LimitZeroPin) == LOW && stepper.distanceToGo() < 0) {
      stepper.setCurrentPosition(0);
      stepper.moveTo(0); 
  }

  stepper.run(); // Sprawdzenie i wykonanie ruchu silnika krokowego, jeśli jest zaplanowany

  // ================= PĘTLA POMIAROWA I-U =================
  static unsigned long lastStepTime = 0;

  if (inSweepingProcess) {

    if (millis() - lastStepTime > 30) {
      
      ledcWrite(0, pwmValue);
      delayMicroseconds(1000); // Czas na przełączenie bramki MOSFET

      float current_I = 0.0f;
      float current_V = 0.0f;
      int retries = 0;
      bool isValid = false;

      // Pomiar napięcia i prądu z uśrednieniem i zabezpieczeniem przed błędnymi odczytami
      while (!isValid && retries < 10) {
        
        float v_sum = 0.0f, i_sum = 0.0f;
        for (int k = 0; k < 5; k++) {
          v_sum += (ina219.getBusVoltage_V() + (ina219.getShuntVoltage_mV() / 1000.0f));
          i_sum += ina219.getCurrent_mA();
          delayMicroseconds(200); // Odstęp między próbkami I2C
        }

        current_V = v_sum / 5.0f;
        current_I = i_sum / 5.0f;

        if (current_I < 0) current_I = 0.0f;
        if (current_V < 0) current_V = 0.0f;

        // Dodatkowe zabezpieczenie: Prąd nie może maleć a napięcie nie może rosnąć
        if (pwmValue == 0 || (current_I >= lastSentI && current_V <= lastSentV)) {
          isValid = true; 
        } else {
          retries++;
          delayMicroseconds(500); // Czas na uregulowanie szumu przed powtórzeniem
        }
      }

        // Wysyłanie danych 
        lastSentI = current_I;
        lastSentV = current_V;

        float current_P = current_V * current_I / 1000.0f;
        Serial.printf("{\"mode\":\"sweep_data\", \"v\":%.2f, \"i\":%.2f, \"p\":%.4f}\n",
                      current_V, current_I, current_P);
    

      int percent = (pwmValue * 100) / 4095;
      Serial.printf("{\"mode\":\"progress\", \"p\":%d}\n", percent);

      // Krok PWM
      pwmValue += 10; 

      if (pwmValue > 4095) {
        inSweepingProcess = false;
        pwmValue = 0;
        ledcWrite(0, 0); 
        Serial.println("{\"mode\":\"sweep_end\"}");
      }

      lastStepTime = millis();
    }
  }

  // ================= ALGORYTM MPPT =================
  static unsigned long lastMpptTime = 0;

  if (!shutdownRequested && inMpptProcess && millis() - lastMpptTime >= 200) {
    ledcWrite(0, pwmValue);
    delayMicroseconds(1000);

    float voltageSum = 0.0f;
    float currentSum = 0.0f;
    for (int k = 0; k < 10; k++) {
      voltageSum += ina219.getBusVoltage_V() + (ina219.getShuntVoltage_mV() / 1000.0f);
      currentSum += ina219.getCurrent_mA();
      delayMicroseconds(200);
    }

    float mpptVoltage = voltageSum / 10.0f;
    float mpptCurrent = currentSum / 10.0f;
    if (mpptVoltage < 0.0f) mpptVoltage = 0.0f;
    if (mpptCurrent < 0.0f) mpptCurrent = 0.0f;
    float mpptPower = mpptVoltage * mpptCurrent / 1000.0f;

    if (hasPreviousMpptPower) {
      if (mpptPower < previousMpptPower - mpptPowerTolerance) {
        mpptDirection = -mpptDirection;
      }

      pwmValue += mpptDirection * mpptStep;
      if (pwmValue < 0) pwmValue = 0;
      if (pwmValue > 4095) pwmValue = 4095;
    } else {
      hasPreviousMpptPower = true;
      pwmValue = mpptStep;
    }

    previousMpptPower = mpptPower;
    Serial.printf("{\"mode\":\"mppt_data\", \"pwm\":%d, \"v\":%.2f, \"i\":%.2f, \"p\":%.4f}\n",
                  pwmValue, mpptVoltage, mpptCurrent, mpptPower);
    lastMpptTime = millis();
  }

  // =================CHŁODZENIE/PI =================
  static unsigned long lastMsg = 0;
  float output = 0.0f;
  int fanPwm = 0;
  int maxOutput = 255; // Maksymalna wartość PWM dla wiatraka
  int minFanPwm = 75; // Minimalna wartość PWM dla wiatraka

  if (!shutdownRequested && !inSweepingProcess && stepper.distanceToGo() == 0 && (millis() - lastMsg > 1000)) {
    unsigned long now = millis();

    float dt = 1.0f;
    if (lastMsg != 0) {
      dt = (now - lastMsg) / 1000.0f;
    }

    sensors.requestTemperatures();
    float currentTemp = sensors.getTempCByIndex(0);
    
    float error = currentTemp - targetTemp;

    float nextIntegral = integral + error * dt;
    float testOutput = (Kp * error) + (Ki * nextIntegral);

    //----------------------Anti-windup--------------------------------------
    if (testOutput > maxOutput) {
      output = maxOutput;
    } else if (testOutput < minFanPwm) {
      output = minFanPwm;
    } else {
      integral = nextIntegral;
      output = testOutput;
    }

    //----------------------Histereza chłodzenia-----------------------------
    static bool fanWorking = false;
    const float hysteresisTop = 1.0f; // zaczynamy chłodzić gdy temperatura wzrośnie powyżej target + 1.0
    const float hysteresisDown = 1.0f;  // przestajemy chłodzić gdy temperatura spadnie poniżej target - 1.0

    if (currentTemp >= targetTemp + hysteresisTop) {
        fanWorking = true;
    } else if (currentTemp <= targetTemp - hysteresisDown) {
        fanWorking = false;
    }
    
    if (!fanWorking) {
      fanPwm = 0;
    } else {
      fanPwm = (int)output;
    }
    //----------------------------------------------------------------------
  
    ledcWrite(2, fanPwm); 

  // Wysyłanie danych statusowych w formacie JSON
    Serial.printf("{\"mode\":\"status\", \"angle\": %.2f, \"temp\": %.2f, \"fan\": %d}\n", 
                  stepper.currentPosition() * 1.8f, 
                  currentTemp,
                  fanPwm);
    lastMsg = now;
  }
}