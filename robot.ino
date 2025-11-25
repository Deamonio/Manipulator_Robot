import pygame
import sys
import math
import serial
import time
import json
import csv
from datetime import datetime
from dataclasses import dataclass
from typing import List, Tuple, Optional
from enum import Enum

# ========================================================================================================
# Configuration & Constants
# ========================================================================================================

class Config:
    """시스템 설정을 관리하는 클래스"""
    PORT = '/dev/ttyUSB0'
    BAUD_RATE = 115200
    SCREEN_WIDTH = 1100
    SCREEN_HEIGHT = 700
    
    KEY_REPEAT_DELAY = 50
    KEY_REPEAT_INTERVAL = 50
    FAST_STEP_SIZE = 2
    SLOW_STEP_SIZE = 1
    
    MOTION_SMOOTHNESS = 0.08
    LOG_INTERVAL = 100

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
    LIGHT_GRAY = (248, 249, 250)
    PANEL_BG = (255, 255, 255)
    CARD_SHADOW = (230, 232, 236)
    ACCENT_BLUE = (59, 130, 246)
    ACCENT_DARK = (37, 99, 235)
    TEXT_DARK = (31, 41, 55)
    TEXT_GRAY = (107, 114, 128)
    TEXT_LIGHT = (156, 163, 175)
    SUCCESS_GREEN = (34, 197, 94)
    WARNING_ORANGE = (251, 146, 60)
    ERROR_RED = (239, 68, 68)
    PROGRESS_BG = (241, 245, 249)
    BORDER_COLOR = (229, 231, 235)
    PRESET_PURPLE = (168, 85, 247)
    TORQUE_ON = (34, 197, 94)
    TORQUE_OFF = (156, 163, 175)

# ========================================================================================================
# Motor Controller Class
# ========================================================================================================

class MotorController:
    """모터 제어를 담당하는 클래스"""
    
    def __init__(self):
        self.motors = [
            MotorConfig(0, "Base", 0, 1023, 512),
            MotorConfig(1, "Shoulder", 512, 960, 512),
            MotorConfig(2, "Upper_Arm", 30, 1010, 512),
            MotorConfig(3, "Elbow", 15, 980, 980),
            MotorConfig(4, "Wrist", 0, 1023, 800),
            MotorConfig(5, "Hand", 430, 890, 430),
        ]
        
        self.current_positions = [m.default_pos for m in self.motors]
        self.target_positions = [m.default_pos for m in self.motors]
        self.motor_states = [MotorState.IDLE] * len(self.motors)
        self.velocities = [0.0] * len(self.motors)
        self.torque_enabled = [True] * len(self.motors)  # 토크 상태 추가
        
        self.presets = self._load_presets()
        self.is_serial_connected = False
        self.arduino = None
        self._init_serial()
        
    def _init_serial(self):
        """시리얼 연결 초기화"""
        try:
            self.arduino = serial.Serial(Config.PORT, Config.BAUD_RATE, timeout=1)
            time.sleep(2)
            print(f"{Colors.BLUE}[Serial]{Colors.END} Connected to Arduino.")
            self.is_serial_connected = True
        except Exception as e:
            print(f"{Colors.BLUE}[Serial]{Colors.END}{Colors.RED}[ERROR]{Colors.END} {e}")
            print(f"{Colors.BLUE}[Serial]{Colors.END} Running in simulation mode.")
        print(f"{Colors.BLUE}[Serial]{Colors.END} Running in simulation mode.")
    
    def _load_presets(self) -> dict:
        """저장된 프리셋 불러오기"""
        try:
            with open('presets.json', 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {
                "Home": [512, 512, 512, 956, 800, 430],
                "Ready": [512, 600, 400, 800, 512, 430],
                "Rest": [512, 512, 800, 600, 512, 890],
            }
    
    def save_preset(self, name: str):
        """현재 위치를 프리셋으로 저장"""
        self.presets[name] = self.target_positions.copy()
        with open('presets.json', 'w') as f:
            json.dump(self.presets, f, indent=2)
        print(f"{Colors.GREEN}[Preset]{Colors.END} Saved '{name}'")
    
    def load_preset(self, name: str) -> bool:
        """프리셋 위치로 이동"""
        if name in self.presets:
            self.target_positions = self.presets[name].copy()
            self.send_control_command()
            return True
        return False
    
    def toggle_torque(self, motor_index: int):
        """모터 토크 토글"""
        self.torque_enabled[motor_index] = not self.torque_enabled[motor_index]
        self.send_torque_command()
        status = "ON" if self.torque_enabled[motor_index] else "OFF"
        print(f"{Colors.CYAN}[Torque]{Colors.END} M{motor_index+1} ({self.motors[motor_index].name}): {status}")
    
    def update_target(self, motor_index: int, direction: str, step_size: int) -> bool:
        """모터 목표 위치 업데이트"""
        motor = self.motors[motor_index]
        old_target = self.target_positions[motor_index]
        
        if direction == "increase":
            new_target = min(motor.max_val, old_target + step_size)
        else:
            new_target = max(motor.min_val, old_target - step_size)
        
        if new_target != old_target:
            self.target_positions[motor_index] = new_target
            
            if new_target == motor.max_val or new_target == motor.min_val:
                self.motor_states[motor_index] = MotorState.AT_LIMIT
            else:
                self.motor_states[motor_index] = MotorState.MOVING
            
            return True
        return False
    
    def update_positions(self):
        """현재 위치를 목표 위치로 부드럽게 이동"""
        for i in range(len(self.motors)):
            diff = self.target_positions[i] - self.current_positions[i]
            
            if abs(diff) > 0.5:
                self.velocities[i] = diff * Config.MOTION_SMOOTHNESS
                self.current_positions[i] += self.velocities[i]
                self.motor_states[i] = MotorState.MOVING
            else:
                self.current_positions[i] = self.target_positions[i]
                self.velocities[i] = 0
                if self.motor_states[i] == MotorState.MOVING:
                    self.motor_states[i] = MotorState.IDLE
    
    def send_control_command(self):
        """위치 제어 명령 전송"""
        positions = [int(pos) for pos in self.target_positions]
        command = f"Control:{','.join(map(str, positions))}*"
        self._send_serial_command(command)
    
    def send_torque_command(self):
        """토크 제어 명령 전송"""
        torque_values = [1 if enabled else 0 for enabled in self.torque_enabled]
        command = f"Torque:{','.join(map(str, torque_values))}*"
        self._send_serial_command(command)
    
    def _send_serial_command(self, command: str):
        """시리얼 명령 전송 공통 함수"""
        if self.is_serial_connected:
            try:
                self.arduino.write(command.encode('utf-8'))
                if self.arduino.in_waiting:
                    response = self.arduino.readline().decode('utf-8').strip()
            except Exception as e:
                print(f"{Colors.RED}[Serial Error]{Colors.END} {e}")
        
        print(f"{Colors.GREEN}[Command]{Colors.END} {command}")

    def get_motor_info(self, motor_index: int) -> dict:
        """모터 정보 반환"""
        motor = self.motors[motor_index]
        return {
            'name': motor.name,
            'current': self.current_positions[motor_index],
            'target': self.target_positions[motor_index],
            'min': motor.min_val,
            'max': motor.max_val,
            'state': self.motor_states[motor_index],
            'velocity': abs(self.velocities[motor_index]),
            'angle': self.target_positions[motor_index] * (300 / 1023),
            'torque_enabled': self.torque_enabled[motor_index]
        }

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
        
        with open(self.filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Timestamp', 'M1', 'M2', 'M3', 'M4', 'M5', 'M6', 'Event'])
    
    def log(self, positions: List[float], event: str = ""):
        """데이터 로깅"""
        current_time = pygame.time.get_ticks()
        
        if not self.enabled or (current_time - self.last_log_time) < Config.LOG_INTERVAL:
            return
        
        self.last_log_time = current_time
        timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
        
        with open(self.filename, 'a', newline='') as f:
            writer = csv.writer(f)
            row = [timestamp] + [int(pos) for pos in positions] + [event]
            writer.writerow(row)

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
        try:
            self.font_title = pygame.font.SysFont("Segoe UI", 26, bold=True)
            self.font_medium = pygame.font.SysFont("Segoe UI", 18, bold=True)
            self.font_small = pygame.font.SysFont("Segoe UI", 14)
            self.font_tiny = pygame.font.SysFont("Segoe UI", 11)
            self.font_large = pygame.font.SysFont("Segoe UI", 36, bold=True)
        except:
            self.font_title = pygame.font.Font(None, 26)
            self.font_medium = pygame.font.Font(None, 18)
            self.font_small = pygame.font.Font(None, 14)
            self.font_tiny = pygame.font.Font(None, 11)
            self.font_large = pygame.font.Font(None, 36)
    
    def draw_rounded_rect(self, color, rect, radius=12):
        """둥근 모서리 사각형"""
        pygame.draw.rect(self.screen, color, rect, border_radius=radius)
    
    def draw_shadow(self, rect, offset=3):
        """그림자 효과"""
        shadow_rect = rect.copy()
        shadow_rect.x += offset
        shadow_rect.y += offset
        self.draw_rounded_rect(UIColors.CARD_SHADOW, shadow_rect, 12)
    
    def draw_motor_gauge(self, x, y, width, height, motor_info: dict, motor_index: int):
        """개선된 모터 게이지 (토크 버튼 포함)"""
        panel_rect = pygame.Rect(x, y, width, height)
        self.draw_shadow(panel_rect, 2)
        self.draw_rounded_rect(UIColors.PANEL_BG, panel_rect)
        
        border_color = UIColors.BORDER_COLOR
        if motor_info['state'] == MotorState.MOVING:
            border_color = UIColors.ACCENT_BLUE
        elif motor_info['state'] == MotorState.AT_LIMIT:
            border_color = UIColors.WARNING_ORANGE
        
        pygame.draw.rect(self.screen, border_color, panel_rect, 2, border_radius=12)
        
        # 헤더
        motor_num = self.font_small.render(f"M{motor_index + 1}", True, UIColors.TEXT_LIGHT)
        self.screen.blit(motor_num, (x + 15, y + 12))
        
        name_text = self.font_medium.render(motor_info['name'], True, UIColors.TEXT_DARK)
        self.screen.blit(name_text, (x + 50, y + 10))
        
        # 토크 버튼
        torque_button_rect = pygame.Rect(x + width - 70, y + 8, 55, 24)
        torque_color = UIColors.TORQUE_ON if motor_info['torque_enabled'] else UIColors.TORQUE_OFF
        self.draw_rounded_rect(torque_color, torque_button_rect, 6)
        
        torque_text = self.font_tiny.render("TORQUE", True, UIColors.WHITE)
        text_x = torque_button_rect.centerx - torque_text.get_width() // 2
        text_y = torque_button_rect.centery - torque_text.get_height() // 2
        self.screen.blit(torque_text, (text_x, text_y))
        
        # 저장: 클릭 감지를 위해
        motor_info['torque_button_rect'] = torque_button_rect
        
        # 현재 값
        value_text = self.font_large.render(f"{int(motor_info['current'])}", True, UIColors.ACCENT_BLUE)
        value_width = value_text.get_width()
        self.screen.blit(value_text, (x + width - value_width - 15, y + 35))
        
        # 속도 표시
        if motor_info['velocity'] > 0.1:
            velocity_text = self.font_tiny.render(f"v: {motor_info['velocity']:.1f}", True, UIColors.TEXT_LIGHT)
            self.screen.blit(velocity_text, (x + width - 60, y + 75))
        
        # 진행 바
        bar_x = x + 15
        bar_y = y + 85
        bar_width = width - 30
        bar_height = 14
        
        bar_bg = pygame.Rect(bar_x, bar_y, bar_width, bar_height)
        self.draw_rounded_rect(UIColors.PROGRESS_BG, bar_bg, 7)
        
        range_span = motor_info['max'] - motor_info['min']
        if range_span > 0:
            progress = (motor_info['current'] - motor_info['min']) / range_span
            filled_width = int(bar_width * progress)
            
            if filled_width > 4:
                filled_rect = pygame.Rect(bar_x, bar_y, filled_width, bar_height)
                
                if progress < 0.33:
                    color = UIColors.ACCENT_BLUE
                elif progress < 0.66:
                    color = UIColors.SUCCESS_GREEN
                else:
                    color = UIColors.WARNING_ORANGE
                
                self.draw_rounded_rect(color, filled_rect, 7)
        
        # 범위 표시
        min_text = self.font_tiny.render(f"{motor_info['min']}", True, UIColors.TEXT_LIGHT)
        self.screen.blit(min_text, (bar_x, bar_y + 18))
        
        max_text = self.font_tiny.render(f"{motor_info['max']}", True, UIColors.TEXT_LIGHT)
        self.screen.blit(max_text, (bar_x + bar_width - max_text.get_width(), bar_y + 18))
        
        angle_text = self.font_tiny.render(f"Angle: {motor_info['angle']:.1f}°", True, UIColors.TEXT_GRAY)
        self.screen.blit(angle_text, (bar_x + bar_width // 2 - 35, bar_y + 18))
    
    def draw_preset_panel(self, x, y, width, height, presets: dict, active_preset: Optional[str]):
        """프리셋 패널"""
        panel_rect = pygame.Rect(x, y, width, height)
        self.draw_shadow(panel_rect, 2)
        self.draw_rounded_rect(UIColors.PANEL_BG, panel_rect)
        pygame.draw.rect(self.screen, UIColors.BORDER_COLOR, panel_rect, 1, border_radius=12)
        
        title = self.font_medium.render("Presets", True, UIColors.TEXT_DARK)
        self.screen.blit(title, (x + 15, y + 15))
        
        button_y = y + 50
        for i, (name, _) in enumerate(presets.items()):
            button_rect = pygame.Rect(x + 15, button_y + i * 40, width - 30, 35)
            
            color = UIColors.PRESET_PURPLE if name == active_preset else UIColors.ACCENT_BLUE
            self.draw_rounded_rect(color, button_rect, 8)
            
            text = self.font_small.render(name, True, UIColors.WHITE)
            text_x = button_rect.centerx - text.get_width() // 2
            text_y = button_rect.centery - text.get_height() // 2
            self.screen.blit(text, (text_x, text_y))
            
            hint = self.font_tiny.render(f"F{i+1}", True, UIColors.TEXT_LIGHT)
            self.screen.blit(hint, (x + width - 35, button_y + i * 40 + 10))
    
    def draw_control_panel(self, status_msg: str, is_connected: bool, is_logging: bool):
        """하단 제어 패널"""
        panel_x = 30
        panel_y = Config.SCREEN_HEIGHT - 140
        panel_width = Config.SCREEN_WIDTH - 60
        panel_height = 110
        
        panel_rect = pygame.Rect(panel_x, panel_y, panel_width, panel_height)
        self.draw_shadow(panel_rect, 2)
        self.draw_rounded_rect(UIColors.PANEL_BG, panel_rect)
        pygame.draw.rect(self.screen, UIColors.BORDER_COLOR, panel_rect, 1, border_radius=12)
        
        status_color = UIColors.SUCCESS_GREEN if is_connected else UIColors.ERROR_RED
        pygame.draw.circle(self.screen, status_color, (panel_x + 20, panel_y + 25), 6)
        
        title = self.font_small.render("Status", True, UIColors.TEXT_GRAY)
        self.screen.blit(title, (panel_x + 35, panel_y + 18))
        
        # 로깅 상태
        if is_logging:
            log_icon = self.font_small.render("● REC", True, UIColors.ERROR_RED)
            self.screen.blit(log_icon, (panel_x + 100, panel_y + 18))
        
        status = self.font_medium.render(status_msg, True, UIColors.TEXT_DARK)
        self.screen.blit(status, (panel_x + 20, panel_y + 45))
        
        hints = [
            "Q/A: M1  W/S: M2  E/D: M3  R/F: M4  T/G: M5  Y/H: M6  [Click Torque Button to Toggle]",
            "F1-F3: Load Preset  Ctrl+F1-F3: Save Preset  L: Log  ESC: Exit"
        ]
        
        for i, hint in enumerate(hints):
            hint_text = self.font_tiny.render(hint, True, UIColors.TEXT_LIGHT)
            self.screen.blit(hint_text, (panel_x + 20, panel_y + 73 + i * 16))

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
        }
        
        self.motor_info_cache = []  # 토크 버튼 클릭 감지용
        
        print(f"{Colors.GREEN}[System]{Colors.END} Robot Control System initialized")
    
    def handle_events(self):
        """이벤트 처리"""
        current_time = pygame.time.get_ticks()
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            
            elif event.type == pygame.MOUSEBUTTONDOWN:
                # 토크 버튼 클릭 체크
                mouse_pos = pygame.mouse.get_pos()
                for i, motor_info in enumerate(self.motor_info_cache):
                    if 'torque_button_rect' in motor_info:
                        if motor_info['torque_button_rect'].collidepoint(mouse_pos):
                            self.controller.toggle_torque(i)
                            self.action_text = f"M{i+1} Torque: {'ON' if self.controller.torque_enabled[i] else 'OFF'}"
            
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                
                elif event.key == pygame.K_l:
                    self.logger.enabled = not self.logger.enabled
                    status = "enabled" if self.logger.enabled else "disabled"
                    self.action_text = f"Logging {status}"
                    print(f"{Colors.CYAN}[Logger]{Colors.END} {status}")
                
                elif event.key in [pygame.K_F1, pygame.K_F2, pygame.K_F3]:
                    mods = pygame.key.get_mods()
                    preset_names = list(self.controller.presets.keys())
                    preset_index = event.key - pygame.K_F1
                    
                    if mods & pygame.KMOD_CTRL:
                        if preset_index < len(preset_names):
                            preset_name = preset_names[preset_index]
                            self.controller.save_preset(preset_name)
                            self.action_text = f"Saved preset: {preset_name}"
                            self.logger.log(self.controller.target_positions, f"Saved: {preset_name}")
                    else:
                        if preset_index < len(preset_names):
                            preset_name = preset_names[preset_index]
                            if self.controller.load_preset(preset_name):
                                self.active_preset = preset_name
                                self.action_text = f"Loaded preset: {preset_name}"
                                self.logger.log(self.controller.target_positions, f"Preset: {preset_name}")
                
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
            
            elif event.type == pygame.KEYUP:
                if event.key in self.keys_pressed:
                    del self.keys_pressed[event.key]
                if event.key in self.last_command_time:
                    del self.last_command_time[event.key]
        
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
        self.controller.update_positions()
        self.logger.log(self.controller.current_positions)
    
    def render(self):
        """화면 렌더링"""
        self.screen.fill(UIColors.LIGHT_GRAY)
        
        header = self.renderer.font_title.render("Manipulator Robot Control", True, UIColors.TEXT_DARK)
        self.screen.blit(header, (30, 25))
        
        subtitle = self.renderer.font_tiny.render(
            f"6-DOF Control System | Logging: {'ON' if self.logger.enabled else 'OFF'}", 
            True, UIColors.TEXT_GRAY
        )
        self.screen.blit(subtitle, (30, 55))
        
        gauge_width = 370
        gauge_height = 120
        spacing = 20
        start_x = 30
        start_y = 90
        
        self.motor_info_cache = []
        for i in range(6):
            row = i // 2
            col = i % 2
            x = start_x + col * (gauge_width + spacing)
            y = start_y + row * (gauge_height + spacing)
            
            motor_info = self.controller.get_motor_info(i)
            self.motor_info_cache.append(motor_info)
            self.renderer.draw_motor_gauge(x, y, gauge_width, gauge_height, motor_info, i)
        
        preset_x = start_x + 2 * (gauge_width + spacing)
        preset_y = start_y
        preset_width = 200
        preset_height = 3 * gauge_height + 2 * spacing
        
        self.renderer.draw_preset_panel(
            preset_x, preset_y, preset_width, preset_height, 
            self.controller.presets, self.active_preset
        )
        
        self.renderer.draw_control_panel(
            self.action_text,
            self.controller.is_serial_connected,
            self.logger.enabled
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
        self.controller.target_positions = [m.default_pos for m in self.controller.motors]
        self.controller.send_control_command()
        print(f"{Colors.YELLOW}[System]{Colors.END} Shutting down...")
        self.action_text = "System Shutdown"
        
        if self.controller.is_serial_connected and self.controller.arduino:
            try:
                self.controller.arduino.close()
                print(f"{Colors.BLUE}[Serial]{Colors.END} Connection closed")
            except:
                pass
        
        pygame.quit()
        sys.exit()

# ========================================================================================================
# Entry Point
# ========================================================================================================

if __name__ == "__main__":
    app = RobotControlApp()
    app.run()
