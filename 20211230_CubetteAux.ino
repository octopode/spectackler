#include <Adafruit_MLX90614.h>
#include "DHT.h"
#include <AFMotor.h>


// pin assignments

// lamp control
const byte pinLamp = 13;

// autopolarizers

//// stepping params
////// period (ms)
float per = 10;
////// type
uint8_t stepType = INTERLEAVE;
////// num steps to rotate polarizer
int nsteps = 28;

//// sensor vars
float hum;
float tem;
float inf;
float amb;

//// two steppers, one on each port
AF_Stepper stepperEx(48, 1);
AF_Stepper stepperEm(48, 2);
AF_Stepper steppers[2] = { stepperEx, stepperEm };

// hygrometer
#define DHTPIN A3
#define DHTTYPE DHT11
DHT hygro(DHTPIN, DHTTYPE);

// IR thermometer uses default pins A4, A5
Adafruit_MLX90614 infra = Adafruit_MLX90614();

void floatDelay(float ms)
{
  unsigned long whole = ms;
  int part = (ms - whole) * 1000;
  delay(whole);
  if (part > 4) delayMicroseconds(part);
}

void rot(int stepperNum, int dir){
  AF_Stepper stepper = steppers[stepperNum];
  for(int i=0; i<26; i+=1){
    stepper.onestep(dir, stepType);
    floatDelay(per);
  }
  stepper.release();
}

void setup() {
  // configure pins
  pinMode(pinLamp, OUTPUT);

  // start comms
  Serial.begin(9600);
  hygro.begin();
  infra.begin();

  // first reading
  hum = hygro.readHumidity();
  tem = hygro.readTemperature();
  inf = infra.readObjectTempC();
  amb = infra.readAmbientTempC();
}

void loop() {
  // wait for serial input
  if(Serial.available()){
    String cmd = Serial.readString();
    cmd.trim();
    // manual index
    if(cmd == "XV"){rot(0, FORWARD ); Serial.println("XV");}
    if(cmd == "XH"){rot(0, BACKWARD); Serial.println("XH");}
    if(cmd == "MV"){rot(1, BACKWARD ); Serial.println("MV");}
    if(cmd == "MH"){rot(1, FORWARD); Serial.println("MH");}
    // poll sensors
    if(cmd == "HUM"){Serial.println(hum);}
    if(cmd == "TEM"){Serial.println(tem);}
    if(cmd == "INF"){Serial.println(inf);}
    if(cmd == "AMB"){Serial.println(amb);}
    // command spec lamp
    if(cmd == "LON"){digitalWrite(pinLamp, HIGH); Serial.println(1);}
    if(cmd == "LOF"){digitalWrite(pinLamp, LOW ); Serial.println(0);}
  }else{
    // this means consecutive serial queries will be processed immediately
    // and also that queries should not be persistent!
    hum = hygro.readHumidity();
    tem = hygro.readTemperature();
    //inf = infra.readObjectTempC();
    //amb = infra.readAmbientTempC();
    // 20220617 workarounds bc I unplugged it :(
    inf = 0;
    amb = 0;
  }
}
