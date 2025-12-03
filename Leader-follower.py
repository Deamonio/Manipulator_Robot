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
 

const uint8_t DXL_ID = 7;
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
#define ID7            (7u)




#define ID11            (11u)
#define ID12            (12u)
#define ID13            (13u)
#define ID14            (14u)
#define ID15            (15u)
#define ID16            (16u)
#define ID17            (17u)





bool passivityMode = false;

int mot1Pos = 512;
int mot2Pos = 512;
int mot3Pos = 380;
int mot4Pos = 800;
int mot5Pos = 700;
int mot6Pos = 512;
int mot7Pos = 512;

int mot11Pos = 512;
int mot12Pos = 512;
int mot13Pos = 380;
int mot14Pos = 800;
int mot15Pos = 700;
int mot16Pos = 512;
int mot17Pos = 512;



int mot1PosRead;
int mot2PosRead;
int mot3PosRead;
int mot4PosRead;
int mot5PosRead;
int mot6PosRead;
int mot7PosRead;



int mot11PosRead;
int mot12PosRead;
int mot13PosRead;
int mot14PosRead;
int mot15PosRead;
int mot16PosRead;
int mot17PosRead;





void setup() {
  // put your setup code here, to run once:
  
  // Use UART port of DYNAMIXEL Shield to debug.
  Serial.begin(115200);
  //while(!DEBUG_SERIAL);

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
  dxl.writeControlTableItem(MOVING_SPEED, ID7, 100);


  dxl.writeControlTableItem(MOVING_SPEED, ID11, 100);
  dxl.writeControlTableItem(MOVING_SPEED, ID12, 100);
  dxl.writeControlTableItem(MOVING_SPEED, ID13, 100);
  dxl.writeControlTableItem(MOVING_SPEED, ID14, 100);
  dxl.writeControlTableItem(MOVING_SPEED, ID15, 100);
  dxl.writeControlTableItem(MOVING_SPEED, ID16, 100);
  dxl.writeControlTableItem(MOVING_SPEED, ID17, 100);


  // Turn off torque when configuring items in EEPROM area
  dxl.torqueOff(ID1);
  dxl.torqueOff(ID2);
  dxl.torqueOff(ID3);
  dxl.torqueOff(ID4);
  dxl.torqueOff(ID5);
  dxl.torqueOff(ID6);
  dxl.torqueOff(ID7);


  dxl.torqueOff(ID11);
  dxl.torqueOff(ID12);
  dxl.torqueOff(ID13);
  dxl.torqueOff(ID14);
  dxl.torqueOff(ID15);
  dxl.torqueOff(ID16);
  dxl.torqueOff(ID17);


  
  dxl.setOperatingMode(ID1, OP_POSITION);
  dxl.setOperatingMode(ID2, OP_POSITION);
  dxl.setOperatingMode(ID3, OP_POSITION);
  dxl.setOperatingMode(ID4, OP_POSITION);
  dxl.setOperatingMode(ID5, OP_POSITION);
  dxl.setOperatingMode(ID6, OP_POSITION);
  dxl.setOperatingMode(ID7, OP_POSITION);

  dxl.setOperatingMode(ID11, OP_POSITION);
  dxl.setOperatingMode(ID12, OP_POSITION);
  dxl.setOperatingMode(ID13, OP_POSITION);
  dxl.setOperatingMode(ID14, OP_POSITION);
  dxl.setOperatingMode(ID15, OP_POSITION);
  dxl.setOperatingMode(ID16, OP_POSITION);
  dxl.setOperatingMode(ID17, OP_POSITION);


  
  dxl.torqueOn(ID1);
  dxl.torqueOn(ID2);
  dxl.torqueOn(ID3);
  dxl.torqueOn(ID4);
  dxl.torqueOn(ID5);
  dxl.torqueOn(ID6);
  dxl.torqueOn(ID7);
  
  dxl.torqueOn(ID11);
  dxl.torqueOn(ID12);
  dxl.torqueOn(ID13);
  dxl.torqueOn(ID14);
  dxl.torqueOn(ID15);
  dxl.torqueOn(ID16);
  dxl.torqueOn(ID17);
  


  //start pos
  dxl.setGoalPosition(ID1, mot1Pos);
  dxl.setGoalPosition(ID2, mot2Pos);
  dxl.setGoalPosition(ID3, mot3Pos);
  dxl.setGoalPosition(ID4, mot4Pos);
  dxl.setGoalPosition(ID5, mot5Pos);
  dxl.setGoalPosition(ID6, mot6Pos);
  dxl.setGoalPosition(ID7, mot7Pos);


  dxl.setGoalPosition(ID11, mot1Pos);
  dxl.setGoalPosition(ID12, mot2Pos);
  dxl.setGoalPosition(ID13, mot3Pos);
  dxl.setGoalPosition(ID14, mot4Pos);
  dxl.setGoalPosition(ID15, mot5Pos);
  dxl.setGoalPosition(ID16, mot6Pos);
  dxl.setGoalPosition(ID17, mot7Pos);

  delay(2000);
  

  //leader motor torque off
  dxl.torqueOff(ID11);
  dxl.torqueOff(ID12);
  dxl.torqueOff(ID13);
  dxl.torqueOff(ID14);
  dxl.torqueOff(ID15);
  dxl.torqueOff(ID16);
  dxl.torqueOff(ID17);
}

void loop() {
  // receiveSerial();
  // if (passivityMode) {
  //   readMotorPos();
  //   printSerial("Feedback");
  //   delay(20);
  // }
  //readMotorPos();
  readMotorPosLeader();
  moveFollower();
  
  printSerial2();
}

void printSerial(String command) {
  Serial.println(command+":"+String(mot1PosRead)+","+String(mot2PosRead)+","+String(mot3PosRead)+","+String(mot4PosRead)+","+String(mot5PosRead)+","+String(mot6PosRead)+","+String(mot7PosRead));
}

void printSerial2() {
  Serial.print("ID11: ");
  Serial.print(mot11PosRead);
  Serial.print(", ID12: ");
  Serial.print(mot12PosRead);
  Serial.print(", ID13: ");
  Serial.print(mot13PosRead);
  Serial.print(", ID14: ");
  Serial.print(mot14PosRead);
  Serial.print(", ID15: ");
  Serial.print(mot15PosRead);
  Serial.print(", ID16: ");
  Serial.print(mot16PosRead);
  Serial.print(", ID17: ");
  Serial.println(mot17PosRead);
}

void moveFollower() {
  // dxl.torqueOn(ID1);
  // dxl.torqueOn(ID2);
  // dxl.torqueOn(ID3);
  // dxl.torqueOn(ID4);
  // dxl.torqueOn(ID5);
  // dxl.torqueOn(ID6);
  // dxl.torqueOn(ID7);

  dxl.setGoalPosition(ID1, mot11PosRead);
  dxl.setGoalPosition(ID2, mot12PosRead);
  dxl.setGoalPosition(ID3, mot13PosRead);
  dxl.setGoalPosition(ID4, mot14PosRead);
  dxl.setGoalPosition(ID5, mot15PosRead);
  dxl.setGoalPosition(ID6, mot16PosRead);
  dxl.setGoalPosition(ID7, mot17PosRead);
}

void readMotorPos() {
  mot1PosRead = dxl.getPresentPosition(ID1);
  mot2PosRead = dxl.getPresentPosition(ID2);
  mot3PosRead = dxl.getPresentPosition(ID3);
  mot4PosRead = dxl.getPresentPosition(ID4);
  mot5PosRead = dxl.getPresentPosition(ID5);
  mot6PosRead = dxl.getPresentPosition(ID6);
  mot7PosRead = dxl.getPresentPosition(ID7);
}

void readMotorPosLeader() {
  mot11PosRead = dxl.getPresentPosition(ID11);
  mot12PosRead = dxl.getPresentPosition(ID12);
  mot13PosRead = dxl.getPresentPosition(ID13);
  mot14PosRead = dxl.getPresentPosition(ID14);
  mot15PosRead = dxl.getPresentPosition(ID15);
  mot16PosRead = dxl.getPresentPosition(ID16);
  mot17PosRead = dxl.getPresentPosition(ID17);
}

void moveMotor() {
    dxl.torqueOn(ID1);
    dxl.torqueOn(ID2);
    dxl.torqueOn(ID3);
    dxl.torqueOn(ID4);
    dxl.torqueOn(ID5);
    dxl.torqueOn(ID6);
    dxl.torqueOn(ID7);

    dxl.setGoalPosition(ID1, mot1Pos);
    dxl.setGoalPosition(ID2, mot2Pos);
    dxl.setGoalPosition(ID3, mot3Pos);
    dxl.setGoalPosition(ID4, mot4Pos);
    dxl.setGoalPosition(ID5, mot5Pos);
    dxl.setGoalPosition(ID6, mot6Pos);
    dxl.setGoalPosition(ID7, mot7Pos);
}

void receiveSerial() {
  if (Serial.available()) {
    int c, n1, n2, n3, n4, n5, n6, n7;

    String packet = Serial.readStringUntil('*');
    
    // int colonIndex = packet.indexOf(':');
    // if (colonIndex == -1) return; // Invalid format
    
    // // Extract command word and data
    // String command = packet.substring(0, colonIndex);
    // String data = packet.substring(colonIndex + 1);
    

    sscanf(packet.c_str(), "%d,%d,%d,%d,%d,%d,%d,%d", &c, &n1, &n2, &n3, &n4, &n5, &n6, &n7); //mot1Pos,mot2Pos,mot3Pos,mot4Pos,mot5Pos,mot6Pos
    
    if (c == 0) {
      // software endstop
      // mot1Pos = constrain(n1, 0, 1023);
      // mot2Pos = constrain(n2, 180, 845);
      // mot3Pos = constrain(n3, 165, 1023);
      // mot4Pos = constrain(n4, 512, 1023);
      // mot5Pos = constrain(n5, 512, 1023);
      // mot6Pos = constrain(n6, 0, 1023);
      // mot7Pos = constrain(n7, 370, 695);

      //do not use software endstop
      mot1Pos = n1;
      mot2Pos = n2;
      mot3Pos = n3;
      mot4Pos = n4;
      mot5Pos = n5;
      mot6Pos = n6;
      mot7Pos = n7;


      moveMotor();
    }
    else if (c == 1) {
      if (n1 ==1) {
        dxl.torqueOn(ID1);
        dxl.torqueOn(ID2);
        dxl.torqueOn(ID3);
        dxl.torqueOn(ID4);
        dxl.torqueOn(ID5);
        dxl.torqueOn(ID6);
        dxl.torqueOn(ID7);
      }
      else if (n1 == 0) {
        dxl.torqueOff(ID1);
        dxl.torqueOff(ID2);
        dxl.torqueOff(ID3);
        dxl.torqueOff(ID4);
        dxl.torqueOff(ID5);
        dxl.torqueOff(ID6);
        dxl.torqueOff(ID7);
      }
    }
    else if (c == 3) {
      readMotorPos();
      printSerial("Positions");
    }
    else if (c == 2) {
      if (n1 ==1) {
        passivityMode = true;
      }
      else if (n1 ==0) {
        passivityMode = false;
      }
    }
    
  }
}
