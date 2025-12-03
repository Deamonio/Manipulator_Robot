#include "Arduino.h"
#include "AX12A.h"

// Dynamixel AX-12A 설정
#define DirectionPin    (10u)
#define BaudRate        (1000000ul)

// 모터 ID 정의
#define ID1             (1u)
#define ID2             (2u)
#define ID3             (3u)
#define ID4             (4u)
#define ID5             (5u)
#define ID6             (6u)

// 모터 위치 변수 (초기값)
int mot1Pos = 512;
int mot2Pos = 512;
int mot3Pos = 512;
int mot4Pos = 980;
int mot5Pos = 800;
int mot6Pos = 430;

// 함수 선언
void moveMotor();
void receiveSerial();
void handleControlCommand(const String& data);
void handleTorqueCommand(const String& data);

void setup() {
  Serial.begin(115200); // PC와의 시리얼 통신
  ax12a.begin(BaudRate, DirectionPin, &Serial1); // AX-12A 통신 (Serial1 사용)

  Serial.println("AX-12A 6-Motor Control Ready");
}

void loop() {
  receiveSerial(); // 시리얼 데이터 수신 및 처리
  moveMotor();     // 모터 위치 명령
}

// 모터 위치 이동 함수
void moveMotor() {
  // 모터 위치 설정
  ax12a.move(ID1, mot1Pos);
  ax12a.move(ID2, mot2Pos);
  ax12a.move(ID3, mot3Pos);
  ax12a.move(ID4, mot4Pos);
  ax12a.move(ID5, mot5Pos);
  ax12a.move(ID6, mot6Pos);

  // 현재 모터 위치를 시리얼로 출력
  Serial.print(mot1Pos); Serial.print(",");
  Serial.print(mot2Pos); Serial.print(",");
  Serial.print(mot3Pos); Serial.print(",");
  Serial.print(mot4Pos); Serial.print(",");
  Serial.print(mot5Pos); Serial.print(",");
  Serial.print(mot6Pos); Serial.println();
}

// 시리얼 데이터 수신 및 커맨드 파싱 함수
void receiveSerial() {
  if (Serial.available()) {
    String packet = Serial.readStringUntil('*'); // '*' 문자까지 데이터 읽기
    
    // 커맨드와 데이터를 ':' 기준으로 분리
    int separatorIndex = packet.indexOf(':');
    
    if (separatorIndex > 0) {
      String command = packet.substring(0, separatorIndex); // Command_Word
      String data = packet.substring(separatorIndex + 1);    // 데이터 (예: 512,512,...)
      
      // 커맨드에 따라 분기 처리
      if (command.equalsIgnoreCase("Control")) {
        handleControlCommand(data);
      } else if (command.equalsIgnoreCase("Torque")) {
        handleTorqueCommand(data);
      } else {
        Serial.print("Unknown Command: ");
        Serial.println(command);
      }
    } else {
      Serial.print("Invalid packet format: ");
      Serial.println(packet);
    }
  }
}

// 'Control' 커맨드 처리 함수 (모터 위치 설정)
void handleControlCommand(const String& data) {
  int n1, n2, n3, n4, n5, n6;
  
  // sscanf를 사용하여 쉼표로 구분된 6개의 정수 파싱
  int count = sscanf(data.c_str(), "%d,%d,%d,%d,%d,%d", &n1, &n2, &n3, &n4, &n5, &n6);
  
  if (count == 6) {
    // 파싱된 값으로 모터 위치 업데이트 및 범위 제한 (constrain)
    mot1Pos = constrain(n1, 0, 1023);
    mot2Pos = constrain(n2, 512, 960);
    mot3Pos = constrain(n3, 30, 1010);
    mot4Pos = constrain(n4, 15, 950);
    mot5Pos = constrain(n5, 0, 1023);
    mot6Pos = constrain(n6, 430, 890);
    
    Serial.println("Control Command Processed.");
  } else {
    Serial.print("Control command data format error. Got ");
    Serial.print(count);
    Serial.println(" values.");
  }
}

// 'Torque' 커맨드 처리 함수 (토크 상태 설정)
void handleTorqueCommand(const String& data) {
  int t1, t2, t3, t4, t5, t6;
  
  // sscanf를 사용하여 쉼표로 구분된 6개의 정수 (0 또는 1) 파싱
  int count = sscanf(data.c_str(), "%d,%d,%d,%d,%d,%d", &t1, &t2, &t3, &t4, &t5, &t6);
  
  if (count == 6) {
    // 각 모터 ID에 토크 상태 설정 (0 또는 1)
    ax12a.torqueStatus(ID1, constrain(t1, 0, 1));
    ax12a.torqueStatus(ID2, constrain(t2, 0, 1));
    ax12a.torqueStatus(ID3, constrain(t3, 0, 1));
    ax12a.torqueStatus(ID4, constrain(t4, 0, 1));
    ax12a.torqueStatus(ID5, constrain(t5, 0, 1));
    ax12a.torqueStatus(ID6, constrain(t6, 0, 1));
    
    Serial.println("Torque Command Processed.");
  } else {
    Serial.print("Torque command data format error. Got ");
    Serial.print(count);
    Serial.println(" values.");
  }
}
