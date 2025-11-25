#include <Dynamixel2Arduino.h>

// Please modify it to suit your hardware.
#if defined(ARDUINO_AVR_UNO) || defined(ARDUINO_AVR_MEGA2560) // When using DynamixelShield
  #include <SoftwareSerial.h>
  SoftwareSerial soft_serial(7, 8); // DYNAMIXELShield UART RX/TX
  #define DXL_SERIAL   Serial
  #define DEBUG_SERIAL soft_serial
  const int DXL_DIR_PIN = 2; // DYNAMIXEL Shield DIR PIN
#elif defined(ARDUINO_SAM_DUE) // When using DynamixelShield
  #define DXL_SERIAL   Serial
  #define DEBUG_SERIAL SerialUSB
  const int DXL_DIR_PIN = 2; // DYNAMIXEL Shield DIR PIN
#elif defined(ARDUINO_SAM_ZERO) // When using DynamixelShield
  #define DXL_SERIAL   Serial1
  #define DEBUG_SERIAL SerialUSB
  const int DXL_DIR_PIN = 2; // DYNAMIXEL Shield DIR PIN
#elif defined(ARDUINO_OpenCM904) // When using official ROBOTIS board with DXL circuit.
  #define DXL_SERIAL   Serial3 //OpenCM9.04 EXP Board's DXL port Serial. (Serial1 for the DXL port on the OpenCM 9.04 board)
  #define DEBUG_SERIAL Serial
  const int DXL_DIR_PIN = 22; //OpenCM9.04 EXP Board's DIR PIN. (28 for the DXL port on the OpenCM 9.04 board)
#elif defined(ARDUINO_OpenCR) // When using official ROBOTIS board with DXL circuit.
  // For OpenCR, there is a DXL Power Enable pin, so you must initialize and control it.
  // Reference link : https://github.com/ROBOTIS-GIT/OpenCR/blob/master/arduino/opencr_arduino/opencr/libraries/DynamixelSDK/src/dynamixel_sdk/port_handler_arduino.cpp#L78
  #define DXL_SERIAL   Serial3
  #define DEBUG_SERIAL Serial
  const int DXL_DIR_PIN = 84; // OpenCR Board's DIR PIN.
#elif defined(ARDUINO_OpenRB)  // When using OpenRB-150
  //OpenRB does not require the DIR control pin.
  #define DXL_SERIAL Serial1
  #define DEBUG_SERIAL Serial
  const int DXL_DIR_PIN = -1;
#else // Other boards when using DynamixelShield
  #define DXL_SERIAL   Serial1
  #define DEBUG_SERIAL Serial
  const int DXL_DIR_PIN = 2; // DYNAMIXEL Shield DIR PIN
#endif
 

const uint8_t DXL_ID = 6;
const float DXL_PROTOCOL_VERSION = 1.0;

Dynamixel2Arduino dxl(DXL_SERIAL, DXL_DIR_PIN);

//This namespace is required to use Control table item names
using namespace ControlTableItem;



#define ID1            (1u)
#define ID2            (2u)
#define ID3            (3u)
#define ID4            (4u)
#define ID5            (5u)
#define ID6            (6u)

bool torqueEn = true;

int mot1Pos = 512;
int mot2Pos = 380;
int mot3Pos = 800;
int mot4Pos = 700;
int mot5Pos = 512;
int mot6Pos = 512;

int mot1PosRead;
int mot2PosRead;
int mot3PosRead;
int mot4PosRead;
int mot5PosRead;
int mot6PosRead;



void setup() {
  // put your setup code here, to run once:
  
  // Use UART port of DYNAMIXEL Shield to debug.
  Serial.begin(115200);
  while(!DEBUG_SERIAL);

  // Set Port baudrate to 57600bps. This has to match with DYNAMIXEL baudrate.
  dxl.begin(1000000);
  // Set Port Protocol Version. This has to match with DYNAMIXEL protocol version.
  dxl.setPortProtocolVersion(DXL_PROTOCOL_VERSION);
  // Get DYNAMIXEL information
  //dxl.ping(DXL_ID);
  // Limit the maximum velocity and max accel in Position Control Mode. Use 0 for Max speed
  dxl.writeControlTableItem(MOVING_SPEED, ID1, 100);
  dxl.writeControlTableItem(MOVING_SPEED, ID2, 100);
  dxl.writeControlTableItem(MOVING_SPEED, ID3, 100);
  dxl.writeControlTableItem(MOVING_SPEED, ID4, 100);
  dxl.writeControlTableItem(MOVING_SPEED, ID5, 100);
  dxl.writeControlTableItem(MOVING_SPEED, ID6, 100);


  // Turn off torque when configuring items in EEPROM area
  dxl.torqueOff(ID1);
  dxl.torqueOff(ID2);
  dxl.torqueOff(ID3);
  dxl.torqueOff(ID4);
  dxl.torqueOff(ID5);
  dxl.torqueOff(ID6);
  
  dxl.setOperatingMode(ID1, OP_POSITION);
  dxl.setOperatingMode(ID2, OP_POSITION);
  dxl.setOperatingMode(ID3, OP_POSITION);
  dxl.setOperatingMode(ID4, OP_POSITION);
  dxl.setOperatingMode(ID5, OP_POSITION);
  dxl.setOperatingMode(ID6, OP_POSITION);
  
  dxl.torqueOn(ID1);
  dxl.torqueOn(ID2);
  dxl.torqueOn(ID3);
  dxl.torqueOn(ID4);
  dxl.torqueOn(ID5);
  dxl.torqueOn(ID6);
  

  
  
  
  
  //start pos
  dxl.setGoalPosition(ID1, mot1Pos);
  dxl.setGoalPosition(ID2, mot2Pos);
  dxl.setGoalPosition(ID3, mot3Pos);
  dxl.setGoalPosition(ID4, mot4Pos);
  dxl.setGoalPosition(ID5, mot5Pos);
  dxl.setGoalPosition(ID6, mot6Pos);
  delay(2000);
  
}

void loop() {
  // put your main code here, to run repeatedly:
  receiveSerial();
  moveMotor();
  readMotorPos();
  //printSerial();
}

void printSerial() {
  Serial.print(mot1PosRead);
  Serial.print(",");
  Serial.print(mot2PosRead);
  Serial.print(",");
  Serial.print(mot3PosRead);
  Serial.print(",");
  Serial.print(mot4PosRead);
  Serial.print(",");
  Serial.print(mot5PosRead);
  Serial.print(",");
  Serial.print(mot6PosRead);
  Serial.println();
}

void readMotorPos() {
  mot1PosRead = dxl.getPresentPosition(ID1);
  mot2PosRead = dxl.getPresentPosition(ID2);
  mot3PosRead = dxl.getPresentPosition(ID3);
  mot4PosRead = dxl.getPresentPosition(ID4);
  mot5PosRead = dxl.getPresentPosition(ID5);
  mot6PosRead = dxl.getPresentPosition(ID6);
}

void moveMotor() {
  if (torqueEn == true) {
    dxl.torqueOn(ID1);
    dxl.torqueOn(ID2);
    dxl.torqueOn(ID3);
    dxl.torqueOn(ID4);
    dxl.torqueOn(ID5);
    dxl.torqueOn(ID6);

    dxl.setGoalPosition(ID1, mot1Pos);
    dxl.setGoalPosition(ID2, mot2Pos);
    dxl.setGoalPosition(ID3, mot3Pos);
    dxl.setGoalPosition(ID4, mot4Pos);
    dxl.setGoalPosition(ID5, mot5Pos);
    dxl.setGoalPosition(ID6, mot6Pos);
  }
  else {
    dxl.torqueOff(ID1);
    dxl.torqueOff(ID2);
    dxl.torqueOff(ID3);
    dxl.torqueOff(ID4);
    dxl.torqueOff(ID5);
    dxl.torqueOff(ID6);
  }
}

void receiveSerial() {
  if (Serial.available()) {
    int n1, n2, n3, n4, n5, n6, n7;
    String packet = Serial.readStringUntil('*');
    sscanf(packet.c_str(), "%d,%d,%d,%d,%d,%d,%d", &n1, &n2, &n3, &n4, &n5, &n6, &n7); //torque,mot1Pos,mot2Pos,mot3Pos,mot4Pos,mot5Pos,mot6Pos
    
    if (n1 == 1) {
      torqueEn = true;
    }
    else {
      torqueEn = false;
    }

    mot1Pos = constrain(n2, 0, 1023);
    mot2Pos = constrain(n3, 380, 1023);
    mot3Pos = constrain(n4, 512, 1023);
    mot4Pos = constrain(n5, 512, 1023);
    mot5Pos = constrain(n6, 0, 1023);
    mot6Pos = constrain(n7, 370, 695);
    
  }
}
