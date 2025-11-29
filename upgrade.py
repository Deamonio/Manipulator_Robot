import pygame
import sys
import math
import serial
import time
import json
import threading
import csv
from datetime import datetime
from dataclasses import dataclass
from typing import List, Tuple, Optional
from enum import Enum
from queue import Queue

# ========================================================================================================
# Configuration & Constants
# ========================================================================================================

class Config:
    """시스템 설정을 관리하는 클래스"""
    # NOTE: /dev/ttyUSB0 대신 사용 환경에 맞는 포트를 지정해야 합니다.
    PORT = '/dev/ttyACM1' 
    BAUD_RATE = 115200
    SCREEN_WIDTH = 1000
    SCREEN_HEIGHT = 720  # 720 -> 750 (여유 공간 확보)
    
    KEY_REPEAT_DELAY = 50
    KEY_REPEAT_INTERVAL = 50
    FAST_STEP_SIZE = 5
    SLOW_STEP_SIZE = 1
    
    MOTION_SMOOTHNESS = 0.08
    LOG_INTERVAL = 100

    PASSIVITY_MODE = False
    DEV_MODE = False

@dataclass
class MotorConfig:
    """개별 모터 설정"""
    index: int
    name: str
    min_val: int
    max_val: int
    default_pos: int
    
class MotorState(Enum):
    """모터 상태"""
    IDLE = "idle"
    MOVING = "moving"
    ERROR = "error"
    AT_LIMIT = "at_limit"

# ========================================================================================================
# Color Schemes
# ========================================================================================================

class Colors:
    """콘솔 출력 색상 코드"""
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    GRAY = '\033[90m'
    BOLD = '\033[1m'
    END = '\033[0m'

class UIColors:
    """PyGame UI 색상 팔레트"""
    WHITE = (255, 255, 255)
    LIGHT_GRAY = (245, 247, 250) # 배경색 변경
    PANEL_BG = (255, 255, 255)
    CARD_SHADOW = (200, 202, 206) # 그림자 색상 변경 (더 옅게)
    ACCENT_BLUE = (37, 99, 235) # 주요 강조색
    ACCENT_DARK = (17, 24, 39)
    TEXT_DARK = (31, 41, 55)
    TEXT_GRAY = (107, 114, 128)
    TEXT_LIGHT = (156, 163, 175)
    SUCCESS_GREEN = (16, 185, 129)
    WARNING_ORANGE = (251, 146, 60)
    ERROR_RED = (239, 68, 68)
    PROGRESS_BG = (229, 231, 235)
    BORDER_COLOR = (229, 231, 235)
    PRESET_PURPLE = (124, 58, 237)
    TORQUE_ON = (34, 197, 94)
    TORQUE_OFF = (107, 114, 128)
    TORQUE_HOVER = (75, 85, 99)

# ========================================================================================================
# Serial Communication Class
# ========================================================================================================

class SerialCommunicator:
    """시리얼 통신을 전담하는 클래스"""
    
    def __init__(self, port: str = Config.PORT, baud_rate: int = Config.BAUD_RATE):
        self.port = port
        self.baud_rate = baud_rate
        self.arduino = None
        self.is_connected = False
        self.running = False
        
        self.receive_queue = Queue()
        self.receive_thread = None
        
        if not Config.DEV_MODE:
            self._connect()
        else:
            print(f"{Colors.YELLOW}[Serial]{Colors.END} DEV_MODE: Serial communication disabled")
    
    def _connect(self):
        """시리얼 포트 연결"""
        try:
            self.arduino = serial.Serial(self.port, self.baud_rate, timeout=1)
            time.sleep(2)
            self.is_connected = True
            print(f"{Colors.BLUE}[Serial]{Colors.END} Connected to {self.port}")
            
            # 수신 스레드 시작
            self.running = True
            self.receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
            self.receive_thread.start()
            
        except Exception as e:
            self.is_connected = False
            print(f"{Colors.BLUE}[Serial]{Colors.END}{Colors.RED}[ERROR]{Colors.END} {e}")
            print(f"{Colors.BLUE}[Serial]{Colors.END} Running in simulation mode.")
    
    def _receive_loop(self):
        """데이터 수신 루프 (백그라운드 스레드)"""
        while self.running and self.is_connected:
            try:
                if self.arduino and self.arduino.in_waiting:
                    data = self.arduino.readline().decode('utf-8').strip()
                    if data:
                        self.receive_queue.put(data)
            except Exception as e:
                print(f"{Colors.RED}[Serial Read]{Colors.END} {e}")
                time.sleep(0.1)
    
    def send(self, command: str) -> bool:
        """명령 전송"""
        if Config.DEV_MODE:
            print(f"{Colors.GREEN}[TX]{Colors.END} {command} (Simulated)")
            return False
        
        if not self.is_connected:
            print(f"{Colors.YELLOW}[Serial]{Colors.END} Not connected (simulated)")
            return False
        
        try:
            self.arduino.write(command.encode('utf-8'))
            print(f"{Colors.GREEN}[TX]{Colors.END} {command}")
            return True
        except Exception as e:
            print(f"{Colors.RED}[Serial TX]{Colors.END} {e}")
            return False
    
    def get_received_data(self) -> Optional[str]:
        """수신 큐에서 데이터 가져오기"""
        if Config.DEV_MODE:
            return None
        
        if not self.receive_queue.empty():
            return self.receive_queue.get()
        return None
    
    def close(self):
        """연결 종료"""
        if Config.DEV_MODE:
            return
        
        self.running = False
        
        if self.receive_thread:
            self.receive_thread.join(timeout=1.0)
        
        if self.arduino and self.is_connected:
            try:
                self.arduino.close()
                print(f"{Colors.BLUE}[Serial]{Colors.END} Connection closed")
            except Exception as e:
                print(f"{Colors.RED}[Serial Close]{Colors.END} {e}")
        
        self.is_connected = False

# ========================================================================================================
# Motor Controller Class
# ========================================================================================================

class MotorController:
    """모터 제어를 담당하는 클래스"""
    
    def __init__(self):
        self.motors = [
            MotorConfig(0, "Base", 0, 1023, 512),
            MotorConfig(1, "Shoulder", 180, 845, 512),
            MotorConfig(2, "Upper_Arm", 165, 1023, 380),
            MotorConfig(3, "Elbow", 512, 1023, 800),
            MotorConfig(4, "forearm", 512, 1023, 700),
            MotorConfig(5, "Wrist", 0, 1023, 512),
            MotorConfig(6, "Hand", 370, 695, 512),
        ]
        
        self.current_positions = [m.default_pos for m in self.motors]
        self.target_positions = [m.default_pos for m in self.motors]
        self.motor_states = [MotorState.IDLE] * len(self.motors)
        self.velocities = [0.0] * len(self.motors)
        self.all_torque_enabled = True
        self.torque_enabled = [True] * len(self.motors)
        self.is_passivity_first = False
        self.passivity_initialized_motors = [False] * 7
        self.last_feedback_log_time = 0  # ✅ 추가: 마지막 로그 시간
        self.feedback_log_interval = 500  # ✅ 추가: 로그 간격 (ms)
        
        # ✅ 추가: Passivity 모드에서 부드러운 UI 업데이트를 위한 변수
        self.display_positions = [m.default_pos for m in self.motors]  # UI 표시용 위치
        self.passivity_smoothness = 0.15  # 부드러운 전환 계수 (0.1~0.2 권장)
        
        self.default_preset = [m.default_pos for m in self.motors]
        self.custom_presets = self._load_custom_presets()
        self.serial = SerialCommunicator()
    
    def _load_custom_presets(self) -> dict:
        """사용자 지정 프리셋 불러오기"""
        try:
            with open('custom_presets.json', 'r') as f:
                presets = json.load(f)
                if len(presets) > 4:
                    presets = dict(list(presets.items())[:4])
                return presets
        except FileNotFoundError:
            # 기본 Custom 프리셋
            return {
                "Custom 1": [512, 512, 380, 800, 700, 512, 512],
                "Custom 2": [512, 512, 380, 800, 700, 512, 512],
                "Custom 3": [512, 512, 380, 800, 700, 512, 512],
                "Custom 4": [512, 512, 380, 800, 700, 512, 512],
            }
    
    def save_custom_preset(self, slot_index: int):
        """현재 위치를 Custom 프리셋으로 저장 (slot_index: 0~3)"""
        if 0 <= slot_index < 4:
            preset_name = f"Custom {slot_index + 1}"
            if not Config.PASSIVITY_MODE:
                self.custom_presets[preset_name] = [int(p) for p in self.target_positions.copy()]
                with open('custom_presets.json', 'w') as f:
                    json.dump(self.custom_presets, f, indent=2)
                print(f"{Colors.GREEN}[Preset]{Colors.END} Saved '{preset_name}'")
                return True
            else:
                # Passivity 모드에서는 즉시 현재 위치 요청
                self.waiting_for_positions = True
                self.passivity_presets = []
                command = f"3,0,0,0,0,0,0,0*"  # 7개 모터
                self.serial.send(command)
                print(f"{Colors.YELLOW}[Preset]{Colors.END} Requesting positions for '{preset_name}'...")
                
                # 응답 대기 (최대 1초)
                timeout = time.time() + 1.0
                while time.time() < timeout:
                    self.process_feedback()
                    if self.passivity_presets:
                        self.custom_presets[preset_name] = [int(p) for p in self.passivity_presets.copy()]
                        with open('custom_presets.json', 'w') as f:
                            json.dump(self.custom_presets, f, indent=2)
                        print(f"{Colors.GREEN}[Preset]{Colors.END} Saved '{preset_name}' in passivity mode")
                        self.passivity_presets = []
                        self.waiting_for_positions = False
                        return True
                    time.sleep(0.01)
                
                self.waiting_for_positions = False
                print(f"{Colors.RED}[Preset]{Colors.END} Failed to save preset - timeout")
                return False
        return False
    
    def load_default_preset(self) -> bool:
        """Default 프리셋으로 이동 - Passivity 모드에서는 비활성화"""
        if Config.PASSIVITY_MODE:
            print(f"{Colors.YELLOW}[Preset]{Colors.END} Cannot load preset in passivity mode")
            return False
        
        self.target_positions = [float(p) for p in self.default_preset.copy()]
        self.send_control_command()
        return True
    
    def load_custom_preset(self, slot_index: int) -> bool:
        """Custom 프리셋으로 이동 - Passivity 모드에서는 비활성화"""
        if Config.PASSIVITY_MODE:
            print(f"{Colors.YELLOW}[Preset]{Colors.END} Cannot load preset in passivity mode")
            return False
        
        if 0 <= slot_index < 4:
            preset_name = f"Custom {slot_index + 1}"
            if preset_name in self.custom_presets:
                self.target_positions = [float(p) for p in self.custom_presets[preset_name].copy()]
                self.send_control_command()
                return True
        return False
    
    def toggle_torque(self, motor_index: int):
        """개별 모터 토크 토글"""
        self.torque_enabled[motor_index] = not self.torque_enabled[motor_index]
        self.send_torque_command()
        status = "ON" if self.torque_enabled[motor_index] else "OFF"
        print(f"{Colors.CYAN}[Torque]{Colors.END} M{motor_index+1} ({self.motors[motor_index].name}): {status}")
    
    def toggle_all_torque(self) -> bool:
        """모든 모터 토크 토글"""
        new_state = not self.all_torque_enabled
        self.all_torque_enabled = new_state
        self.torque_enabled = [new_state] * len(self.motors)
        self.send_torque_command()

        Config.PASSIVITY_MODE = not new_state
        if Config.PASSIVITY_MODE:
            self.is_passivity_first = True
            self.passivity_initialized_motors = [False] * 7  # 초기화
            # 수정된 명령 형식 (n1만 사용)
            self.serial.send("2,1,0,0,0,0,0,0*")  # passivity on
        else:
            self.is_passivity_first = False
            self.passivity_initialized_motors = [False] * 7
            self.serial.send("2,0,0,0,0,0,0,0*")  # passivity off
        
        status = "enabled" if new_state else "disabled"
        print(f"{Colors.YELLOW}[Torque]{Colors.END} ALL motors torque {status}")
        
        return new_state
    
    def update_target(self, motor_index: int, direction: str, step_size: int) -> bool:
        """모터 목표 위치 업데이트 - Passivity 모드에서는 비활성화"""
        if Config.PASSIVITY_MODE:
            return False
        
        if not (0 <= motor_index < len(self.motors)):
            return False
        
        motor = self.motors[motor_index]
        old_target = self.target_positions[motor_index]
        
        if direction == "increase":
            new_target = min(motor.max_val, old_target + step_size)
        else:
            new_target = max(motor.min_val, old_target - step_size)
        
        if new_target == old_target:
            if new_target == motor.max_val or new_target == motor.min_val:
                self.motor_states[motor_index] = MotorState.AT_LIMIT
            return False
        
        self.target_positions[motor_index] = new_target
        
        if new_target == motor.max_val or new_target == motor.min_val:
            self.motor_states[motor_index] = MotorState.AT_LIMIT
        else:
            self.motor_states[motor_index] = MotorState.MOVING
        
        return True
    
    def update_positions(self):
        """현재 위치를 목표 위치로 부드럽게 이동 (시뮬레이션 + Passivity UI)"""
        
        if not Config.PASSIVITY_MODE:
            # ✅ 일반 모드: 항상 부드러운 시뮬레이션 적용 (UI 반응성)
            for i in range(len(self.motors)):
                diff = self.target_positions[i] - self.current_positions[i]
                
                if abs(diff) > 0.5:
                    self.velocities[i] = diff * Config.MOTION_SMOOTHNESS
                    self.current_positions[i] += self.velocities[i]
                    self.motor_states[i] = MotorState.MOVING
                else:
                    self.current_positions[i] = self.target_positions[i]
                    self.velocities[i] = 0.0
                    if self.motor_states[i] == MotorState.MOVING:
                        self.motor_states[i] = MotorState.IDLE
        
        # ✅ 실제 연결 시에는 피드백으로 current_positions를 보정
        # process_feedback()에서 실제 위치 수신 시 current_positions 덮어씀
        else:
            # ✅ Passivity 모드: display_positions를 target_positions로 부드럽게 이동
            for i in range(len(self.motors)):
                diff = self.target_positions[i] - self.display_positions[i]
                
                if abs(diff) > 0.5:
                    # 부드러운 전환
                    self.display_positions[i] += diff * self.passivity_smoothness
                else:
                    self.display_positions[i] = self.target_positions[i]
            
            # current_positions를 display_positions와 동기화 (UI용)
            self.current_positions = self.display_positions.copy()
    
    def send_control_command(self):
        """위치 제어 명령 전송 - Passivity 모드에서는 비활성화"""
        if Config.PASSIVITY_MODE:
            return
        positions = [int(pos) for pos in self.target_positions]
        command = f"0,{','.join(map(str, positions))}*"
        self.serial.send(command)
    
    def send_torque_command(self):
        """토크 제어 명령 전송"""
        torque_values = [1 if enabled else 0 for enabled in self.torque_enabled]
        command = f"1,{','.join(map(str, torque_values))}*"
        self.serial.send(command)
    
    def process_feedback(self):
        """피드백 데이터 처리 (매 프레임 호출) - 개선된 버전"""
        data = self.serial.get_received_data()
        if data:
            try:
                if data.startswith("Positions:"):
                    parts = data[len("Positions:"):].split(',')
                    positions = [int(p) for p in parts]
                    
                    if self.waiting_for_positions:
                        self.passivity_presets = positions
                        print(f"{Colors.CYAN}[RX Positions]{Colors.END} Received positions for preset save")
                    else:
                        print(f"{Colors.CYAN}[RX Positions]{Colors.END} {positions}")
                
                elif data.startswith("Feedback:"):
                    parts = data[len("Feedback:"):].split(',')
                    
                    if len(parts) < len(self.motors):
                        print(f"{Colors.RED}[Feedback Parse]{Colors.END} Incomplete data: {len(parts)}/7 motors")
                        return
                    
                    # ✅ 개선: 모든 모터 데이터를 먼저 검증
                    new_positions = []
                    parse_success = True
                    
                    for i in range(len(self.motors)):
                        try:
                            new_pos = float(parts[i])
                            new_positions.append(new_pos)
                        except (ValueError, IndexError) as e:
                            print(f"{Colors.RED}[Feedback Parse]{Colors.END} Motor {i+1}: {e}")
                            parse_success = False
                            break
                    
                    if not parse_success:
                        return
                    
                    # ✅ 개선: 데이터 처리 로직
                    if not Config.PASSIVITY_MODE:
                        # 일반 모드: 실시간 피드백으로 current_positions 업데이트
                        for i in range(len(self.motors)):
                            self.current_positions[i] = new_positions[i]
                            
                            # 모터 상태 업데이트
                            if abs(self.current_positions[i] - self.target_positions[i]) < 2:
                                self.motor_states[i] = MotorState.IDLE
                            else:
                                self.motor_states[i] = MotorState.MOVING
                    else:
                        # Passivity 모드: 각 모터별 개별 초기화 후 부드러운 추적
                        for i in range(len(self.motors)):
                            if not self.passivity_initialized_motors[i]:
                                # 첫 수신 데이터로 동기화
                                self.current_positions[i] = new_positions[i]
                                self.target_positions[i] = new_positions[i]
                                self.display_positions[i] = new_positions[i]
                                self.passivity_initialized_motors[i] = True
                                print(f"{Colors.GREEN}[Passivity Init]{Colors.END} Motor {i+1} synced: {new_positions[i]:.1f}")
                            else:
                                # 목표 위치만 업데이트 (UI는 부드럽게 따라감)
                                self.target_positions[i] = new_positions[i]
                            
                            self.motor_states[i] = MotorState.IDLE
                    
                    # ✅ 개선: 로그 출력 제어 (정확한 시간 기반)
                    current_time = pygame.time.get_ticks()
                    if current_time - self.last_feedback_log_time >= self.feedback_log_interval:
                        mode_str = "Passivity" if Config.PASSIVITY_MODE else "Normal"
                        pos_str = ', '.join([f"M{i+1}:{int(p)}" for i, p in enumerate(new_positions)])
                        print(f"{Colors.CYAN}[RX Feedback ({mode_str})]{Colors.END} {pos_str}")
                        self.last_feedback_log_time = current_time
                    
                    # 모든 모터 초기화 완료 확인
                    if self.is_passivity_first and all(self.passivity_initialized_motors):
                        self.is_passivity_first = False
                        print(f"{Colors.GREEN}[Passivity Mode]{Colors.END} All motors synchronized")
                
                else:
                    print(f"{Colors.CYAN}[RX]{Colors.END} {data}")
            except Exception as e:
                print(f"{Colors.RED}[Feedback Parse]{Colors.END} {e}")
    
    def get_motor_info(self, motor_index: int) -> dict:
        """모터 정보 반환"""
        motor = self.motors[motor_index]
        
        # ✅ 개선: Passivity 모드에서는 display_positions 사용
        if Config.PASSIVITY_MODE:
            current_pos = self.display_positions[motor_index]
        else:
            current_pos = self.current_positions[motor_index]
        
        # 각도 계산 (0-1023 범위를 0-300도로 변환)
        angle = (current_pos / 1023.0) * 300.0
        
        return {
            'index': motor_index,
            'name': motor.name,
            'current': current_pos,
            'target': self.target_positions[motor_index],
            'min': motor.min_val,
            'max': motor.max_val,
            'angle': angle,
            'state': self.motor_states[motor_index],
            'velocity': abs(self.velocities[motor_index]) if not Config.PASSIVITY_MODE else 0,
            'torque_enabled': self.torque_enabled[motor_index]
        }
    
    def are_all_torque_enabled(self) -> bool:
        """모든 모터 토크 활성화 여부"""
        return all(self.torque_enabled)
    
    def is_connected(self) -> bool:
        """시리얼 연결 상태 확인"""
        return self.serial.is_connected
    
    def shutdown(self):
        """컨트롤러 종료"""
        print(f"{Colors.YELLOW}[Controller]{Colors.END} Shutting down motors...")
        
        # 기본 위치로 복귀
        self.target_positions = [m.default_pos for m in self.motors]
        self.send_control_command()
        
        # Serial 연결 종료
        self.serial.close()
        
        print(f"{Colors.GREEN}[Controller]{Colors.END} Motors reset to default positions")

# ========================================================================================================
# Data Logger Class
# ========================================================================================================

class DataLogger:
    """모터 데이터 로깅"""
    
    def __init__(self, filename: str = None):
        if filename is None:
            filename = f"robot_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        self.filename = filename
        self.last_log_time = 0
        self.enabled = True
        
        try:
            with open(self.filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Timestamp:  ','M1_Pos', 'M2_Pos', 'M3_Pos', 'M4_Pos', 'M5_Pos', 'M6_Pos', 'Event'])
            print(f"{Colors.GREEN}[Logger]{Colors.END} Log file created: {self.filename}")
        except Exception as e:
            print(f"{Colors.RED}[Logger Error]{Colors.END} Could not create log file: {e}")
            self.enabled = False
    
    def log(self, positions: List[float], event: str = ""):
        """데이터 로깅"""
        current_time = pygame.time.get_ticks()
        
        if not self.enabled or (current_time - self.last_log_time) < Config.LOG_INTERVAL:
            return
        
        self.last_log_time = current_time
        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        
        try:
            with open(self.filename, 'a', newline='') as f:
                writer = csv.writer(f)
                row = [timestamp] + [int(pos) for pos in positions] + [event]
                writer.writerow(row)
        except Exception as e:
            # 로깅 실패 시 콘솔 출력만
            print(f"{Colors.RED}[Logger Write Error]{Colors.END} {e}")

# ========================================================================================================
# UI Renderer Class
# ========================================================================================================

class UIRenderer:
    """UI 렌더링을 담당하는 클래스"""
    
    def __init__(self, screen):
        self.screen = screen
        self._init_fonts()
        
    def _init_fonts(self):
        """폰트 초기화"""
        # 폰트명은 시스템 환경에 따라 다를 수 있으므로 Fallback을 사용합니다.
        font_name = pygame.font.get_default_font()
        if sys.platform == 'win32' or sys.platform == 'cygwin':
            font_name = "malgungothic" # 맑은 고딕 선호 (Windows)
        elif sys.platform == 'darwin':
            font_name = "AppleGothic" # Apple Gothic 선호 (macOS)
        
        try:
            self.font_title = pygame.font.SysFont(font_name, 30, bold=True)
            self.font_medium = pygame.font.SysFont(font_name, 20, bold=True)
            self.font_small = pygame.font.SysFont(font_name, 16)
            self.font_tiny = pygame.font.SysFont(font_name, 12)
            self.font_large = pygame.font.SysFont(font_name, 40, bold=True)
        except:
            # Fallback to default
            self.font_title = pygame.font.Font(None, 30)
            self.font_medium = pygame.font.Font(None, 20)
            self.font_small = pygame.font.Font(None, 16)
            self.font_tiny = pygame.font.Font(None, 12)
            self.font_large = pygame.font.Font(None, 40)
    
    def draw_rounded_rect(self, color, rect, radius=12, border_width=0, border_color=None):
        """둥근 모서리 사각형"""
        # Pygame의 border_radius는 완벽한 둥근 모서리를 구현하기 어려울 수 있습니다.
        # 여기서는 Pygame 기본 기능을 사용합니다.
        pygame.draw.rect(self.screen, color, rect, border_radius=radius)
        if border_width > 0 and border_color:
            # 외곽선 그리기 (배경색과 겹치지 않게)
            pygame.draw.rect(self.screen, border_color, rect, border_width, border_radius=radius)
    
    def draw_shadow(self, rect, offset=3, alpha=80): # offset과 alpha 조정
        """그림자 효과 (Surface를 이용한 개선된 그림자)"""
        # 그림자 효과를 위해 원본 Rect보다 약간 큰 Surface를 생성
        shadow_rect = rect.copy()
        
        # 그림자 위치를 offset만큼 이동
        shadow_x = rect.x + offset
        shadow_y = rect.y + offset
        
        # 그림자 색상 (UIColors.CARD_SHADOW)과 투명도(alpha)
        color = UIColors.CARD_SHADOW
        shadow_color = (color[0], color[1], color[2], alpha)
        
        # 그림자 표면을 직접 그리기
        shadow_surface = pygame.Surface((shadow_rect.width, shadow_rect.height), pygame.SRCALPHA)
        pygame.draw.rect(shadow_surface, shadow_color, (0, 0, shadow_rect.width, shadow_rect.height), border_radius=12)
        
        self.screen.blit(shadow_surface, (shadow_x, shadow_y))
    
    def draw_motor_gauge(self, x, y, width, height, motor_info: dict, motor_index: int):
        """개선된 모터 게이지 - 완전한 오버플로우 방지"""
        panel_rect = pygame.Rect(x, y, width, height)
        
        # 그림자 및 배경
        self.draw_shadow(panel_rect, 3, 150)
        
        border_color = UIColors.BORDER_COLOR
        if motor_info['state'] == MotorState.MOVING:
            border_color = UIColors.ACCENT_BLUE
        elif motor_info['state'] == MotorState.AT_LIMIT:
            border_color = UIColors.WARNING_ORANGE
            
        self.draw_rounded_rect(UIColors.PANEL_BG, panel_rect, radius=10, border_width=2, border_color=border_color)
        
        # 내부 여백 정의
        inner_padding = 10
        inner_width = width - (inner_padding * 2)
        
        # 1. 헤더 (M# / Name)
        motor_num_text = self.font_tiny.render(f"M{motor_index + 1}", True, UIColors.TEXT_LIGHT)
        
        # 이름 길이 제한 (폭 기반 자동 축소)
        motor_name = motor_info['name']
        name_text = self.font_small.render(motor_name, True, UIColors.ACCENT_DARK)
        
        # 이름이 너무 길면 축소
        available_width = inner_width - motor_num_text.get_width() - 30 - 40  # 30=간격, 40=토크 인디케이터
        if name_text.get_width() > available_width:
            # 글자 수 줄이기
            while name_text.get_width() > available_width and len(motor_name) > 3:
                motor_name = motor_name[:-1]
                name_text = self.font_small.render(motor_name + ".", True, UIColors.ACCENT_DARK)
        
        self.screen.blit(motor_num_text, (x + inner_padding, y + 10))
        self.screen.blit(name_text, (x + inner_padding + 28, y + 8))
        
        # 토크 상태 인디케이터 (우측 상단)
        torque_indicator_x = x + width - inner_padding - 10
        torque_indicator_y = y + 16
        torque_color = UIColors.SUCCESS_GREEN if motor_info['torque_enabled'] else UIColors.ERROR_RED
        pygame.draw.circle(self.screen, torque_color, (torque_indicator_x, torque_indicator_y), 6)
        
        # 2. 현재 값 및 각도 (좌우 배치)
        
        # 좌측: 현재 위치 (큰 숫자)
        value_text = self.font_medium.render(f"{int(motor_info['current'])}", True, UIColors.ACCENT_BLUE)
        self.screen.blit(value_text, (x + inner_padding, y + 35))
        
        # 목표 위치 (작은 텍스트)
        target_text = self.font_tiny.render(f"Target: {int(motor_info['target'])}", True, UIColors.TEXT_GRAY)
        self.screen.blit(target_text, (x + inner_padding, y + 65))
        
        # 우측: 각도 표시
        angle_text = self.font_small.render(f"{motor_info['angle']:.1f}°", True, UIColors.ACCENT_DARK)
        angle_x = x + width - inner_padding - angle_text.get_width()
        self.screen.blit(angle_text, (angle_x, y + 42))
        
        # 3. 진행 바
        bar_x = x + inner_padding
        bar_y = y + 88
        bar_width = inner_width
        bar_height = 12
        
        bar_bg = pygame.Rect(bar_x, bar_y, bar_width, bar_height)
        self.draw_rounded_rect(UIColors.PROGRESS_BG, bar_bg, 6)
        
        range_span = motor_info['max'] - motor_info['min']
        if range_span > 0:
            progress = (motor_info['current'] - motor_info['min']) / range_span
            progress = max(0, min(1, progress))
            filled_width = int(bar_width * progress)
            
            # 진행 바 색상
            if progress < 0.1 or progress > 0.9:
                color = UIColors.ERROR_RED
            elif progress < 0.25 or progress > 0.75:
                color = UIColors.WARNING_ORANGE
            else:
                color = UIColors.SUCCESS_GREEN

            if filled_width > 4:
                filled_rect = pygame.Rect(bar_x, bar_y, filled_width, bar_height)
                self.draw_rounded_rect(color, filled_rect, 6)
        
        # 범위 표시
        min_text = self.font_tiny.render(f"{motor_info['min']}", True, UIColors.TEXT_GRAY)
        self.screen.blit(min_text, (bar_x, bar_y + bar_height + 2))
        
        max_text = self.font_tiny.render(f"{motor_info['max']}", True, UIColors.TEXT_GRAY)
        max_x = bar_x + bar_width - max_text.get_width()
        self.screen.blit(max_text, (max_x, bar_y + bar_height + 2))
    
    def draw_torque_control_panel(self, x, y, width, height, all_torque_enabled: bool):
        """토크 제어 패널 - 크기 축소"""
        panel_rect = pygame.Rect(x, y, width, height)
        self.draw_shadow(panel_rect, 3, 150)
        self.draw_rounded_rect(UIColors.PANEL_BG, panel_rect, radius=10, border_width=1, border_color=UIColors.BORDER_COLOR)
        
        inner_padding = 12
        
        # 제목
        title = self.font_small.render("Torque Control", True, UIColors.ACCENT_DARK)
        self.screen.blit(title, (x + inner_padding, y + 10))
        
        # 토크 버튼
        button_rect = pygame.Rect(x + inner_padding, y + 35, width - inner_padding * 2, 42)
        
        # 버튼 색상
        base_color = UIColors.TORQUE_ON if all_torque_enabled else UIColors.TORQUE_OFF
        
        # 마우스 오버 효과
        mouse_pos = pygame.mouse.get_pos()
        is_hover = button_rect.collidepoint(mouse_pos)
        
        if is_hover:
            base_color = tuple(min(255, c + 30) for c in base_color)
        
        self.draw_shadow(button_rect, 2, 100)
        self.draw_rounded_rect(base_color, button_rect, 7)
        
        # 텍스트
        status_text = "TORQUE ON" if all_torque_enabled else "TORQUE OFF"
        status_surface = self.font_small.render(status_text, True, UIColors.WHITE)
        
        # 중앙 정렬
        status_x = button_rect.centerx - status_surface.get_width() // 2
        status_y = button_rect.centery - status_surface.get_height() // 2
        self.screen.blit(status_surface, (status_x, status_y))

        # 힌트 텍스트
        hint = self.font_tiny.render("Z or Click", True, UIColors.TEXT_GRAY)
        hint_x = x + width // 2 - hint.get_width() // 2
        hint_y = y + 85
        self.screen.blit(hint, (hint_x, hint_y))
        
        return button_rect
    
    def draw_preset_panel(self, x, y, width, height, default_preset: List[int], 
                          custom_presets: dict, active_preset: Optional[str]):
        """프리셋 패널 - 하단 정리 버전"""
        panel_rect = pygame.Rect(x, y, width, height)
        self.draw_shadow(panel_rect, 3, 150)
        self.draw_rounded_rect(UIColors.PANEL_BG, panel_rect, radius=10, border_width=1, border_color=UIColors.BORDER_COLOR)
        
        inner_padding = 12
        
        # 제목
        title = self.font_small.render("Quick Presets", True, UIColors.ACCENT_DARK)
        self.screen.blit(title, (x + inner_padding, y + 10))
        
        save_hint = self.font_tiny.render("Ctrl+F2-F5: Save", True, UIColors.TEXT_GRAY)
        self.screen.blit(save_hint, (x + inner_padding, y + 28))
        
        # 프리셋 버튼들
        button_y = y + 50
        button_height = 32
        button_spacing = 8
        
        button_rects = []
        mouse_pos = pygame.mouse.get_pos()
        
        # 1. Default 프리셋 (F1)
        default_rect = pygame.Rect(x + inner_padding, button_y, width - inner_padding * 2, button_height)
        button_rects.append({'rect': default_rect, 'name': 'Default', 'type': 'default', 'index': -1})
        
        is_active = (active_preset == 'Default')
        color = (34, 197, 94) if is_active else (22, 163, 74)
        border_color = (21, 128, 61) if is_active else (22, 101, 52)
        
        if default_rect.collidepoint(mouse_pos):
            color = tuple(min(255, c + 25) for c in color)
        
        self.draw_shadow(default_rect, 2, 100)
        self.draw_rounded_rect(color, default_rect, 5)
        pygame.draw.rect(self.screen, border_color, default_rect, 1, border_radius=5)
        
        # Default 텍스트
        text = self.font_small.render("Default", True, UIColors.WHITE)
        text_x = x + inner_padding + 10
        text_y = default_rect.centery - text.get_height() // 2
        self.screen.blit(text, (text_x, text_y))
        
        hint = self.font_tiny.render("F1", True, UIColors.WHITE)
        self.screen.blit(hint, (x + width - inner_padding - 25, button_y + 10))
        
        button_y += button_height + button_spacing
        
        # 구분선
        divider_y = button_y + 6
        
        custom_label = self.font_tiny.render("CUSTOM", True, UIColors.TEXT_LIGHT)
        label_width = custom_label.get_width()
        label_x = x + width // 2 - label_width // 2
        self.screen.blit(custom_label, (label_x, divider_y - 5))
        
        line_margin = 6
        left_line_start = x + inner_padding + 10
        left_line_end = label_x - line_margin
        right_line_start = label_x + label_width + line_margin
        right_line_end = x + width - inner_padding - 10
        
        pygame.draw.line(self.screen, UIColors.BORDER_COLOR, 
                        (left_line_start, divider_y), 
                        (left_line_end, divider_y), 1)
        
        pygame.draw.line(self.screen, UIColors.BORDER_COLOR, 
                        (right_line_start, divider_y), 
                        (right_line_end, divider_y), 1)
        
        button_y += 18
        
        # 2. Custom 프리셋 4개
        custom_preset_names = [f"Custom {i+1}" for i in range(4)]
        
        for i, preset_name in enumerate(custom_preset_names):
            custom_rect = pygame.Rect(x + inner_padding, button_y + i * (button_height + button_spacing), 
                                     width - inner_padding * 2, button_height)
            button_rects.append({'rect': custom_rect, 'name': preset_name, 'type': 'custom', 'index': i})
            
            is_active = (active_preset == preset_name)
            color = (147, 51, 234) if is_active else (124, 58, 237)
            border_color = (126, 34, 206) if is_active else (109, 40, 217)
            
            if custom_rect.collidepoint(mouse_pos):
                color = tuple(min(255, c + 20) for c in color)
            
            self.draw_shadow(custom_rect, 2, 100)
            self.draw_rounded_rect(color, custom_rect, 5)
            pygame.draw.rect(self.screen, border_color, custom_rect, 1, border_radius=5)
            
            text = self.font_small.render(preset_name, True, UIColors.WHITE)
            text_x = custom_rect.centerx - text.get_width() // 2
            text_y = custom_rect.centery - text.get_height() // 2
            self.screen.blit(text, (text_x, text_y))
            
            hint = self.font_tiny.render(f"F{i+2}", True, UIColors.WHITE)
            self.screen.blit(hint, (x + width - inner_padding - 25, button_y + i * (button_height + button_spacing) + 10))
        
        # 마지막 버튼 아래 여백 (패널 끝 - 더 이상 빈 공간 없음)
        # button_y + 3 * (button_height + button_spacing) + button_height + 10 = 대략 280px
        
        return button_rects
    
    def draw_control_panel(self, panel_y: int, status_msg: str, is_connected: bool, is_logging: bool, log_filename: str):
        """하단 제어 패널 - 완전한 오버플로우 방지"""
        panel_x = 15
        panel_width = Config.SCREEN_WIDTH - 30
        panel_height = 105
        
        panel_rect = pygame.Rect(panel_x, panel_y, panel_width, panel_height)
        self.draw_shadow(panel_rect, 3, 100)
        self.draw_rounded_rect(UIColors.PANEL_BG, panel_rect, radius=10, border_width=1, border_color=UIColors.BORDER_COLOR)
        
        inner_padding = 20
        section_width = (panel_width - inner_padding * 2) // 3
        
        # === 좌측 영역: 시스템 상태 ===
        left_section_x = panel_x + inner_padding
        
        # 연결 상태 인디케이터
        status_color = UIColors.SUCCESS_GREEN if is_connected else UIColors.ERROR_RED
        pygame.draw.circle(self.screen, status_color, (left_section_x, panel_y + 22), 7)
        
        # 시스템 상태 텍스트
        status_title = self.font_small.render("System Status", True, UIColors.ACCENT_DARK)
        self.screen.blit(status_title, (left_section_x + 20, panel_y + 15))
        
        status_text_str = "Connected" if is_connected else "Simulation"
        status_detail = self.font_tiny.render(status_text_str, True, UIColors.TEXT_GRAY)
        self.screen.blit(status_detail, (left_section_x + 20, panel_y + 38))
        
        # 마지막 동작
        action_label = self.font_tiny.render("Last Action:", True, UIColors.TEXT_LIGHT)
        self.screen.blit(action_label, (left_section_x + 20, panel_y + 58))
        
        # 액션 텍스트 폭 제한
        max_width = section_width - 30
        truncated_msg = status_msg
        action_detail = self.font_small.render(truncated_msg, True, UIColors.ACCENT_BLUE)
        
        while action_detail.get_width() > max_width and len(truncated_msg) > 10:
            truncated_msg = truncated_msg[:-4] + "..."
            action_detail = self.font_small.render(truncated_msg, True, UIColors.ACCENT_BLUE)
        
        self.screen.blit(action_detail, (left_section_x + 20, panel_y + 75))
        
        # 구분선
        divider1_x = panel_x + section_width + inner_padding
        pygame.draw.line(self.screen, UIColors.BORDER_COLOR, 
                         (divider1_x, panel_y + 15), 
                         (divider1_x, panel_y + panel_height - 15), 2)
        
        # === 중앙 영역: 데이터 로깅 ===
        center_section_x = divider1_x + inner_padding
        
        # 로깅 상태
        log_title = self.font_small.render("Data Logging", True, UIColors.ACCENT_DARK)
        self.screen.blit(log_title, (center_section_x, panel_y + 15))
        
        log_status_icon = "●" if is_logging else "○"
        log_status_text = f"{log_status_icon} {'Rec' if is_logging else 'Paused'}"
        log_status_color = UIColors.ERROR_RED if is_logging else UIColors.TEXT_GRAY
        
        log_status = self.font_tiny.render(log_status_text, True, log_status_color)
        self.screen.blit(log_status, (center_section_x, panel_y + 38))
        
        # 파일명
        filename_short = log_filename
        log_file = self.font_tiny.render(filename_short, True, UIColors.TEXT_GRAY)
        
        # 파일명 폭 제한
        while log_file.get_width() > section_width - 20 and len(filename_short) > 15:
            filename_short = "..." + filename_short[-15:]
            log_file = self.font_tiny.render(filename_short, True, UIColors.TEXT_GRAY)
        
        log_file_label = self.font_tiny.render("File:", True, UIColors.TEXT_LIGHT)
        self.screen.blit(log_file_label, (center_section_x, panel_y + 58))
        self.screen.blit(log_file, (center_section_x, panel_y + 75))
        
        # 구분선
        divider2_x = divider1_x + section_width + inner_padding
        pygame.draw.line(self.screen, UIColors.BORDER_COLOR, 
                         (divider2_x, panel_y + 15), 
                         (divider2_x, panel_y + panel_height - 15), 2)
        
        # === 우측 영역: 키보드 단축키 ===
        right_section_x = divider2_x + inner_padding
        
        shortcuts_title = self.font_small.render("Controls", True, UIColors.ACCENT_DARK)
        self.screen.blit(shortcuts_title, (right_section_x, panel_y + 15))
        
        shortcuts = [
            ("Q/A W/S E/D", "M1-3"),
            ("R/F T/G Y/H", "M4-6"),
            ("U/J", "M7"),
            ("Shift", "Fine"),
        ]
        
        shortcut_y = panel_y + 38
        for key, desc in shortcuts:
            key_text = self.font_tiny.render(key, True, UIColors.ACCENT_BLUE)
            desc_text = self.font_tiny.render(f"- {desc}", True, UIColors.TEXT_GRAY)
            
            self.screen.blit(key_text, (right_section_x, shortcut_y))
            self.screen.blit(desc_text, (right_section_x + 78, shortcut_y))
            shortcut_y += 14

# ========================================================================================================
# Main Application Class
# ========================================================================================================

class RobotControlApp:
    """메인 애플리케이션 클래스"""
    
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((Config.SCREEN_WIDTH, Config.SCREEN_HEIGHT))
        pygame.display.set_caption("Manipulator Robot Control System")
        
        self.controller = MotorController()
        self.renderer = UIRenderer(self.screen)
        self.logger = DataLogger()
        
        self.clock = pygame.time.Clock()
        self.running = True
        
        self.keys_pressed = {}
        self.last_command_time = {}
        self.action_text = "System Ready"
        self.active_preset = None
        
        self.key_mapping = {
            pygame.K_q: (0, "increase"), pygame.K_a: (0, "decrease"),
            pygame.K_w: (1, "increase"), pygame.K_s: (1, "decrease"),
            pygame.K_e: (2, "increase"), pygame.K_d: (2, "decrease"),
            pygame.K_r: (3, "increase"), pygame.K_f: (3, "decrease"),
            pygame.K_t: (4, "increase"), pygame.K_g: (4, "decrease"),
            pygame.K_y: (5, "increase"), pygame.K_h: (5, "decrease"),
            pygame.K_u: (6, "increase"), pygame.K_j: (6, "decrease"),  # 7번 모터 추가
        }
        
        self.motor_info_cache = []
        self.preset_rects_cache = []
        self.torque_button_rect_cache = None  # 통합 토크 버튼 영역 저장
        
        print(f"{Colors.GREEN}[System]{Colors.END} Robot Control System initialized")
    
    def handle_events(self):
        """이벤트 처리"""
        current_time = pygame.time.get_ticks()
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            
            elif event.type == pygame.MOUSEBUTTONDOWN:
                mouse_pos = pygame.mouse.get_pos()
                
                # 1. 통합 토크 버튼 클릭 체크 (항상 활성)
                if self.torque_button_rect_cache and self.torque_button_rect_cache.collidepoint(mouse_pos):
                    new_state = self.controller.toggle_all_torque()
                    self.action_text = f"ALL Motors Torque: {'ON' if new_state else 'OFF'}"
                    # if not new_state:
                    #     self.action_text += " (Passivity Mode)"
                
                # 2. 프리셋 버튼 클릭 체크
                if not Config.PASSIVITY_MODE:
                    # 일반 모드: 로드 및 저장 가능
                    for preset_data in self.preset_rects_cache:
                        if preset_data['rect'].collidepoint(mouse_pos):
                            preset_name = preset_data['name']
                            preset_type = preset_data['type']
                            preset_index = preset_data['index']
                            
                            mods = pygame.key.get_mods()
                            
                            if preset_type == 'default':
                                if self.controller.load_default_preset():
                                    self.active_preset = 'Default'
                                    self.action_text = f"Loaded preset: Default"
                                    self.logger.log(self.controller.target_positions, "Preset: Default")
                            
                            elif preset_type == 'custom':
                                if mods & pygame.KMOD_CTRL:
                                    self.controller.save_custom_preset(preset_index)
                                    self.action_text = f"Saved preset: {preset_name}"
                                    self.logger.log(self.controller.target_positions, f"Saved: {preset_name}")
                                else:
                                    if self.controller.load_custom_preset(preset_index):
                                        self.active_preset = preset_name
                                        self.action_text = f"Loaded preset: {preset_name}"
                                        self.logger.log(self.controller.target_positions, f"Preset: {preset_name}")
                else:
                    # Passivity 모드: 저장만 가능
                    for preset_data in self.preset_rects_cache:
                        if preset_data['rect'].collidepoint(mouse_pos):
                            preset_name = preset_data['name']
                            preset_type = preset_data['type']
                            preset_index = preset_data['index']
                            
                            mods = pygame.key.get_mods()
                            
                            if preset_type == 'custom' and (mods & pygame.KMOD_CTRL):
                                if self.controller.save_custom_preset(preset_index):
                                    self.action_text = f"Saved preset: {preset_name} (Passivity)"
                                    self.logger.log(self.controller.target_positions, f"Saved: {preset_name}")
                                else:
                                    self.action_text = f"Failed to save preset: {preset_name}"
                            else:
                                self.action_text = "Preset loading disabled in Passivity Mode"
            
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                
                elif event.key == pygame.K_l:
                    self.logger.enabled = not self.logger.enabled
                    status = "enabled" if self.logger.enabled else "disabled"
                    self.action_text = f"Logging {status}"
                    print(f"{Colors.CYAN}[Logger]{Colors.END} {status}")
                
                # T 키로 전체 토크 토글 (항상 활성)
                elif event.key == pygame.K_z and not (pygame.key.get_mods() & (pygame.KMOD_CTRL | pygame.KMOD_SHIFT)):
                    new_state = self.controller.toggle_all_torque()
                    self.action_text = f"ALL Motors Torque: {'ON' if new_state else 'OFF'}"
                    # if not new_state:
                    #     self.action_text += " (Passivity Mode)"
                
                # Passivity 모드가 아닐 때만 프리셋 로드 허용
                elif not Config.PASSIVITY_MODE:
                    # F1: Default 프리셋
                    if event.key == pygame.K_F1:
                        if self.controller.load_default_preset():
                            self.active_preset = 'Default'
                            self.action_text = f"Loaded preset: Default"
                            self.logger.log(self.controller.target_positions, "Preset: Default")
                    
                    # F2-F5: Custom 프리셋 (로드)
                    elif event.key in [pygame.K_F2, pygame.K_F3, pygame.K_F4, pygame.K_F5]:
                        mods = pygame.key.get_mods()
                        slot_index = event.key - pygame.K_F2
                        preset_name = f"Custom {slot_index + 1}"
                        
                        if not (mods & pygame.KMOD_CTRL):
                            if self.controller.load_custom_preset(slot_index):
                                self.active_preset = preset_name
                                self.action_text = f"Loaded preset: {preset_name}"
                                self.logger.log(self.controller.target_positions, f"Preset: {preset_name}")
                    
                    # 모터 제어 키 (일반 모드에서만)
                    elif event.key in self.key_mapping and event.key not in self.keys_pressed:
                        motor_index, direction = self.key_mapping[event.key]
                        
                        mods = pygame.key.get_mods()
                        step_size = Config.SLOW_STEP_SIZE if mods & pygame.KMOD_SHIFT else Config.FAST_STEP_SIZE
                        
                        if self.controller.update_target(motor_index, direction, step_size):
                            self.controller.send_control_command()
                            motor_info = self.controller.get_motor_info(motor_index)
                            self.action_text = f"M{motor_index+1} ({motor_info['name']}): {int(motor_info['target'])}"
                            self.active_preset = None
                        
                        self.keys_pressed[event.key] = True
                        self.last_command_time[event.key] = current_time + Config.KEY_REPEAT_DELAY
                
                # Passivity 모드에서 프리셋 저장 (Ctrl+F2~F5)
                elif Config.PASSIVITY_MODE:
                    if event.key in [pygame.K_F2, pygame.K_F3, pygame.K_F4, pygame.K_F5]:
                        mods = pygame.key.get_mods()
                        if mods & pygame.KMOD_CTRL:
                            slot_index = event.key - pygame.K_F2
                            preset_name = f"Custom {slot_index + 1}"
                            
                            if self.controller.save_custom_preset(slot_index):
                                self.action_text = f"Saved preset: {preset_name} (Passivity)"
                                self.logger.log(self.controller.target_positions, f"Saved: {preset_name}")
                            else:
                                self.action_text = f"Failed to save preset: {preset_name}"
                    else:
                        # Passivity 모드에서 다른 키 입력 차단
                        if event.key in self.key_mapping or event.key == pygame.K_F1:
                            self.action_text = "Motor control disabled in Passivity Mode"
            
            elif event.type == pygame.KEYUP:
                if event.key in self.keys_pressed:
                    del self.keys_pressed[event.key]
                if event.key in self.last_command_time:
                    del self.last_command_time[event.key]
        
        # 키 반복 처리 (Passivity 모드에서는 비활성화)
        if not Config.PASSIVITY_MODE:
            for key in list(self.keys_pressed.keys()):
                if key in self.key_mapping and current_time >= self.last_command_time.get(key, 0):
                    motor_index, direction = self.key_mapping[key]
                    mods = pygame.key.get_mods()
                    step_size = Config.SLOW_STEP_SIZE if mods & pygame.KMOD_SHIFT else Config.FAST_STEP_SIZE
                    
                    if self.controller.update_target(motor_index, direction, step_size):
                        self.controller.send_control_command()
                    
                    self.last_command_time[key] = current_time + Config.KEY_REPEAT_INTERVAL
    
    def update(self):
        """상태 업데이트"""
        self.controller.process_feedback()
        self.controller.update_positions() # 시뮬레이션 모드에서만 부드러운 움직임 적용
        self.logger.log(self.controller.current_positions)
    
    def render(self):
        """화면 렌더링 - 레이아웃 최적화"""
        self.screen.fill(UIColors.LIGHT_GRAY)
        
        # ===== 레이아웃 상수 =====
        PADDING = 15
        SPACING = 12
        
        # 모터 게이지 (2열 4행) - 폭 증가
        GAUGE_WIDTH = 360  # 340 -> 360 (20px 증가)
        GAUGE_HEIGHT = 120
        
        # 우측 패널
        RIGHT_PANEL_WIDTH = 230
        TORQUE_PANEL_HEIGHT = 110
        PRESET_PANEL_HEIGHT = 280  # 320 -> 280 (하단 여백 제거)
        
        # 하단 패널
        CONTROL_PANEL_HEIGHT = 105
        
        # ===== 1. 헤더 =====
        header = self.renderer.font_title.render("Manipulator Robot Control Dashboard", True, UIColors.ACCENT_DARK)
        self.screen.blit(header, (PADDING, PADDING))
        
        subtitle = self.renderer.font_tiny.render(
            f"7-DOF Control System | Dev: {Config.DEV_MODE} | Passivity: {Config.PASSIVITY_MODE}", 
            True, UIColors.TEXT_GRAY
        )
        self.screen.blit(subtitle, (PADDING, PADDING + 35))
        
        # ===== 2. 모터 게이지 섹션 (2열 4행) =====
        gauge_start_x = PADDING
        gauge_start_y = PADDING + 60
        
        self.motor_info_cache = []
        for i in range(7):  # 7개 모터
            row = i // 2  # 2열 배치
            col = i % 2
            
            x = gauge_start_x + col * (GAUGE_WIDTH + SPACING)
            y = gauge_start_y + row * (GAUGE_HEIGHT + SPACING)
            
            motor_info = self.controller.get_motor_info(i)
            self.motor_info_cache.append(motor_info)
            self.renderer.draw_motor_gauge(x, y, GAUGE_WIDTH, GAUGE_HEIGHT, motor_info, i)
        
        # ===== 3. 우측 패널 영역 =====
        right_panel_x = gauge_start_x + 2 * GAUGE_WIDTH + SPACING * 2
        right_panel_y = gauge_start_y
        
        # 3-1. 토크 제어 패널 (상단)
        self.torque_button_rect_cache = self.renderer.draw_torque_control_panel(
            right_panel_x, right_panel_y, RIGHT_PANEL_WIDTH, TORQUE_PANEL_HEIGHT,
            self.controller.all_torque_enabled
        )
        
        # 3-2. 프리셋 패널 (중단) - 고정 높이
        preset_y = right_panel_y + TORQUE_PANEL_HEIGHT + SPACING
        
        self.preset_rects_cache = self.renderer.draw_preset_panel(
            right_panel_x, preset_y, RIGHT_PANEL_WIDTH, PRESET_PANEL_HEIGHT, 
            self.controller.default_preset,
            self.controller.custom_presets, 
            self.active_preset
        )
        
        # ===== 4. 하단 제어 패널 =====
        # 모터 게이지 영역의 실제 높이 계산
        motor_section_bottom = gauge_start_y + 4 * GAUGE_HEIGHT + 3 * SPACING
        
        # 하단 패널 위치 (모터 섹션과 충분한 간격)
        panel_y = motor_section_bottom + SPACING + 5  # 여유 5px 추가
        
        # 화면을 벗어나는 경우 방지
        if panel_y + CONTROL_PANEL_HEIGHT > Config.SCREEN_HEIGHT - PADDING:
            panel_y = Config.SCREEN_HEIGHT - CONTROL_PANEL_HEIGHT - PADDING
        
        self.renderer.draw_control_panel(
            panel_y,
            self.action_text,
            self.controller.is_connected(),
            self.logger.enabled,
            self.logger.filename
        )
        
        pygame.display.flip()
    
    def run(self):
        """메인 루프"""
        while self.running:
            self.handle_events()
            self.update()
            self.render()
            self.clock.tick(60)
        
        self.shutdown()
    
    def shutdown(self):
        """종료 처리"""
        print(f"{Colors.YELLOW}[System]{Colors.END} Shutting down...")
        self.action_text = "System Shutdown"
        
        self.controller.shutdown()
        
        pygame.quit()
        sys.exit()

# ========================================================================================================
# Startup Banner
# ========================================================================================================

def print_banner():
    """시작 배너 출력"""
    banner = f"""
{Colors.CYAN}════════════════════════════════════════════════════════════════════════════════

  {Colors.BLUE}███╗   ███╗ █████╗ ███╗   ██╗██╗██████╗ ██╗   ██╗██╗      █████╗ ████████╗{Colors.CYAN}
  {Colors.BLUE}████╗ ████║██╔══██╗████╗  ██║██║██╔══██╗██║   ██║██║     ██╔══██╗╚══██╔══╝{Colors.CYAN}
  {Colors.BLUE}██╔████╔██║███████║██╔██╗ ██║██║██████╔╝██║   ██║██║     ███████║   ██║{Colors.CYAN}
  {Colors.BLUE}██║╚██╔╝██║██╔══██║██║╚██╗██║██║██╔═══╝ ██║   ██║██║     ██╔══██║   ██║{Colors.CYAN}
  {Colors.BLUE}██║ ╚═╝ ██║██║  ██║██║ ╚████║██║██║     ╚██████╔╝███████╗██║  ██║   ██║{Colors.CYAN}
  {Colors.BLUE}╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝╚═╝╚═╝       ╚═════╝ ╚══════╝╚═╝  ╚═╝   ╚═╝{Colors.CYAN}

  {Colors.GREEN}██████╗  ██████╗ ██████╗  ██████╗ ████████╗{Colors.CYAN}
  {Colors.GREEN}██╔══██╗██╔═══██╗██╔══██╗██╔═══██╗╚══██╔══╝{Colors.CYAN}
  {Colors.GREEN}██████╔╝██║  ██║██████╔╝██║  ██║   ██║{Colors.CYAN}
  {Colors.GREEN}██╔══██╗██║  ██║██╔══██╗██║  ██║   ██║{Colors.CYAN}
  {Colors.GREEN}██║  ██║╚██████╔╝██████╔╝╚██████╔╝   ██║{Colors.CYAN}
  {Colors.GREEN}╚═╝  ╚═╝ ╚═════╝ ╚═════╝  ╚═════╝    ╚═╝{Colors.CYAN}

  {Colors.YELLOW}7-DOF Robotic Arm Control System{Colors.CYAN}
  {Colors.WHITE}Version 2.1 | Python + PyGame + Serial Communication{Colors.CYAN}

════════════════════════════════════════════════════════════════════════════════{Colors.END}
"""
    print(banner)

def select_mode():
    """모드 선택"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}[MODE SELECTION]{Colors.END}\n")
    print(f"{Colors.GREEN}[1]{Colors.END} Production Mode    - Full Serial Communication (Requires connected device)")
    print(f"{Colors.YELLOW}[2]{Colors.END} Development Mode - Serial Communication Disabled (UI Only)\n")
    
    while True:
        try:
            choice = input(f"{Colors.CYAN}Select mode (1/2):{Colors.END} ").strip()
            
            if choice == '1':
                Config.DEV_MODE = False
                print(f"\n{Colors.GREEN}✓ Production Mode Selected{Colors.END}")
                print(f"{Colors.WHITE}Initializing serial communication...{Colors.END}\n")
                time.sleep(1)
                return
            elif choice == '2':
                Config.DEV_MODE = True
                print(f"\n{Colors.YELLOW}✓ Development Mode Selected{Colors.END}")
                print(f"{Colors.WHITE}Serial communication will be disabled. Motor positions will be simulated.{Colors.END}\n")
                time.sleep(1)
                return
            else:
                print(f"{Colors.RED}Invalid input. Please enter 1 or 2.{Colors.END}")
        except KeyboardInterrupt:
            print(f"\n\n{Colors.RED}Startup cancelled by user.{Colors.END}")
            sys.exit(0)
        except Exception as e:
            print(f"{Colors.RED}Error: {e}{Colors.END}")

# ========================================================================================================
# Entry Point
# ========================================================================================================

if __name__ == "__main__":
    print_banner()
    select_mode()
    app = RobotControlApp()
    app.run()
