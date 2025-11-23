import pygame
import sys
import math
import serial
import time

# --- [1. 직렬 통신 및 환경 설정] ---
PORT = '/dev/ttyUSB0'   # Arduino가 연결된 직렬 포트 경로 (Linux/macOS 기준)
BaudRate = 115200       # Arduino와 통신할 전송 속도
SCREEN_WIDTH = 900      
SCREEN_HEIGHT = 650     

# 모터 제어 값 범위 [Min, Max] (하드웨어에 따라 달라짐)
# M1: Base, M2: Shoulder, M3: Apear_Arm, M4: Elbow, M5: Wrist, M6: Hand
motor_ranges = [(0,1023), (512,634), (104,924), (512,956), (0,1023), (430,890)] 

# 현재 모터 위치 (시뮬레이션용). 실제 모터의 엔코더/센서 값에 해당
motor_angles = [512, 512, 512, 956, 800, 430] 
# 목표 모터 위치 (사용자가 키보드로 조작하는 값)
motor_targets = [512, 512, 512, 956, 800, 430]  
motor_names = ["Base", "Shoulder", "Apear_Arm", "Elbow", "Wrist", "Hand"]
action_text = "System Ready" # 하단 제어판에 표시될 현재 상태/액션 메시지

# 키보드 반복 입력을 처리하기 위한 변수
keys_pressed = {}       # 현재 눌려 있는 키 저장
last_command_time = {}  # 마지막으로 명령을 보낸 시간 저장
KEY_REPEAT_DELAY = 50   # 키를 누른 후 첫 반복이 시작되기까지의 시간 (ms)
KEY_REPEAT_INTERVAL = 50 # 반복 명령을 보낼 간격 (ms)

# --- [2. Arduino 직렬 포트 연결] ---
try:
    arduino = serial.Serial(PORT, BaudRate, timeout=1)  # 직렬 포트 연결 시도
    time.sleep(2)  # Arduino가 초기화될 시간을 대기
    print("Connected to Arduino.")

except serial.SerialException as e:
    # 연결 실패 시 오류 메시지 출력 후 프로그램 종료
    print(f"Serial port connection error: {e}")
    # exit() # Pygame 환경에서 실행 오류 방지를 위해 주석 처리

# --- [3. Pygame 초기화 및 GUI 설정] ---
pygame.init()

screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Manipulator Robot")

# 색상 팔레트 정의 (세련된 대시보드 디자인을 위해)
WHITE = (255, 255, 255)         
LIGHT_GRAY = (248, 249, 250)    # 배경색
PANEL_BG = (255, 255, 255)      # 패널 배경색
CARD_SHADOW = (230, 232, 236)   # 카드 그림자색
ACCENT_BLUE = (59, 130, 246)    # 강조색 (파랑)
ACCENT_LIGHT = (147, 197, 253)  
TEXT_DARK = (31, 41, 55)        
TEXT_GRAY = (107, 114, 128)     
TEXT_LIGHT = (156, 163, 175)    
SUCCESS_GREEN = (34, 197, 94)   # 성공/중간 범위
WARNING_ORANGE = (251, 146, 60) # 경고/위험 범위
PROGRESS_BG = (241, 245, 249)   
BORDER_COLOR = (229, 231, 235)  

# 폰트 설정 (Segoe UI 선호, 없으면 기본 폰트 사용)
try:
    font_title = pygame.font.SysFont("Segoe UI", 24, bold=True)
    font_medium = pygame.font.SysFont("Segoe UI", 18, bold=True) 
    font_small = pygame.font.SysFont("Segoe UI", 14)
    font_tiny = pygame.font.SysFont("Segoe UI", 12)
    font_large_num = pygame.font.SysFont("Segoe UI", 32, bold=True)
    print("Using system font: Segoe UI")
except:
    # 시스템 폰트 로드 실패 시 Pygame 기본 폰트 사용
    font_title = pygame.font.Font(None, 24)
    font_medium = pygame.font.Font(None, 18)
    font_small = pygame.font.Font(None, 14)
    font_tiny = pygame.font.Font(None, 12)
    font_large_num = pygame.font.Font(None, 32)
    print("Using Pygame default font.")

# --- [4. GUI 그리기 보조 함수] ---

def draw_gradient_background():
    """연한 회색 배경을 채웁니다."""
    screen.fill(LIGHT_GRAY)

def draw_rounded_rect(surface, color, rect, radius=12):
    """지정된 반지름으로 둥근 사각형을 그립니다."""
    pygame.draw.rect(surface, color, rect, border_radius=radius)

def draw_shadow(surface, rect, offset=3):
    """패널 아래에 그림자 효과를 그립니다."""
    shadow_rect = rect.copy()
    shadow_rect.x += offset
    shadow_rect.y += offset
    draw_rounded_rect(surface, CARD_SHADOW, shadow_rect, 12)

def draw_motor_gauge(x, y, width, height, motor_index):
    """
    개별 모터의 상태를 시각화하는 게이지 카드를 그립니다.
    (x, y): 카드 좌상단 위치, (width, height): 카드 크기, motor_index: 모터 인덱스 (0~5)
    """
    angle = motor_angles[motor_index]
    target = motor_targets[motor_index]
    name = motor_names[motor_index]
    min_val, max_val = motor_ranges[motor_index]
    
    # 1. 카드 패널 그리기 (그림자 -> 배경색 -> 테두리 순)
    panel_rect = pygame.Rect(x, y, width, height)
    draw_shadow(screen, panel_rect, 2)
    draw_rounded_rect(screen, PANEL_BG, panel_rect)
    pygame.draw.rect(screen, BORDER_COLOR, panel_rect, 1, border_radius=12)
    
    # 2. 텍스트 정보 표시
    motor_num = font_small.render(f"M{motor_index + 1}", True, TEXT_LIGHT) # 모터 번호
    screen.blit(motor_num, (x + 15, y + 12))
    
    name_text = font_medium.render(name, True, TEXT_DARK) # 모터 이름 (Base, Shoulder 등)
    screen.blit(name_text, (x + 45, y + 10))
    
    angle_text = font_large_num.render(f"{int(angle)}", True, ACCENT_BLUE) # 현재 각도/위치 값
    angle_width = angle_text.get_width()
    screen.blit(angle_text, (x + width - angle_width - 15, y + 8))
    
    # 3. 진행률 막대 (Progress Bar) 그리기
    bar_x = x + 15
    bar_y = y + 55
    bar_width = width - 30
    bar_height = 12
    
    bar_bg_rect = pygame.Rect(bar_x, bar_y, bar_width, bar_height)
    draw_rounded_rect(screen, PROGRESS_BG, bar_bg_rect, 6) # 배경 막대
    
    range_span = max_val - min_val
    if range_span > 0:
        # 현재 값이 전체 범위에서 차지하는 비율 계산
        progress = (angle - min_val) / range_span 
    else:
        progress = 0
        
    filled_width = int(bar_width * progress)
    
    # 채워진 막대 그리기
    if filled_width > 4: 
        filled_rect = pygame.Rect(bar_x, bar_y, filled_width, bar_height)
        
        # 진행률에 따른 색상 변경 (0.33: 파랑, 0.66: 초록, 그 이상: 주황)
        if progress < 0.33:
            color = ACCENT_BLUE
        elif progress < 0.66:
            color = SUCCESS_GREEN
        else:
            color = WARNING_ORANGE
            
        draw_rounded_rect(screen, color, filled_rect, 6)
    
    # 4. 범위 및 목표 값 텍스트 표시
    range_text = font_tiny.render(f"{min_val}", True, TEXT_LIGHT) # 최소값
    screen.blit(range_text, (bar_x, bar_y + 18))
    
    range_text_end = font_tiny.render(f"{max_val}", True, TEXT_LIGHT) # 최대값
    range_end_width = range_text_end.get_width()
    screen.blit(range_text_end, (bar_x + bar_width - range_end_width, bar_y + 18))
    
    target_text = font_tiny.render(f"Target: {int(target)}", True, TEXT_GRAY) # 목표 값
    screen.blit(target_text, (bar_x + bar_width // 2 - 30, bar_y + 18))

def draw_control_panel():
    """화면 하단의 상태 및 제어 힌트 패널을 그립니다."""
    panel_x = 30
    panel_y = SCREEN_HEIGHT - 120
    panel_width = SCREEN_WIDTH - 60
    panel_height = 90
    
    panel_rect = pygame.Rect(panel_x, panel_y, panel_width, panel_height)
    draw_shadow(screen, panel_rect, 2)
    draw_rounded_rect(screen, PANEL_BG, panel_rect)
    pygame.draw.rect(screen, BORDER_COLOR, panel_rect, 1, border_radius=12)
    
    # 상태 표시기 (녹색 점)
    pygame.draw.circle(screen, SUCCESS_GREEN, (panel_x + 20, panel_y + 25), 5)
    
    title_text = font_small.render("Status", True, TEXT_GRAY)
    screen.blit(title_text, (panel_x + 35, panel_y + 18))
    
    status_text = font_medium.render(action_text, True, TEXT_DARK) # 현재 동작 상태 메시지
    screen.blit(status_text, (panel_x + 20, panel_y + 40))
    
    # M1~M6 키보드 힌트 업데이트
    hint_text_main = font_tiny.render("Q/A: M1 | W/S: M2 | E/D: M3 | R/F: M4", True, TEXT_LIGHT)
    hint_text_aux = font_tiny.render("T/G: M5 | Y/H: M6 | ESC: Exit", True, TEXT_LIGHT) 
    
    screen.blit(hint_text_main, (panel_x + 20, panel_y + 68))
    screen.blit(hint_text_aux, (panel_x + panel_width - hint_text_aux.get_width() - 20, panel_y + 68))


# --- [5. 모터 제어 및 통신 로직] ---

def update_motor_angles():
    """
    현재 각도(motor_angles)가 목표 각도(motor_targets)를 부드럽게 따라가도록 시뮬레이션합니다.
    (실제 로봇의 움직임을 흉내냄)
    **수정: range(6)으로 변경**
    """
    for i in range(len(motor_targets)): # 6개 모터 모두 반영
        diff = motor_targets[i] - motor_angles[i]
        if abs(diff) > 0.5:
            # 목표와의 차이의 10%만큼 이동 (부드러운 감속/보간 효과)
            motor_angles[i] += diff * 0.1  
        else:
            # 목표에 충분히 가까워지면 정확히 목표 값으로 설정
            motor_angles[i] = motor_targets[i]

def send_command():
    """
    현재의 6개 모터 목표 위치를 직렬 포트를 통해 Arduino로 전송합니다.
    **수정: f-string 괄호 오류 수정**
    """
    try:
        # 명령어 형식: "M1,M2,M3,M4,M5,M6*" (예: "625,495,265,512,800,430*")
        # 6번째 모터 값의 괄호 오류 수정: {(int(motor_targets[5])}* command = f"{int(motor_targets[0])},{int(motor_targets[1])},{int(motor_targets[2])},{int(motor_targets[3])},{int(motor_targets[4])},{int(motor_targets[5])}*"
        command = f"{int(motor_targets[0])},{int(motor_targets[1])},{int(motor_targets[2])},{int(motor_targets[3])},{int(motor_targets[4])},{int(motor_targets[5])}*"
        arduino.write(command.encode('utf-8')) # 문자열을 바이트로 인코딩하여 전송
        print(f"Data sent: {command}")
        
        # Arduino로부터의 응답을 읽음 (옵션)
        if arduino.in_waiting:
            response = arduino.readline().decode('utf-8').strip()
            print(f"Arduino response: {response}")

    except Exception as e:
        print(f"Error during communication: {e}")

def update_robot_action(action, motor_index=None, direction=None, step_size=1):
    """
    모터 목표 위치를 업데이트하고, 명령을 전송하며, 상태 텍스트를 갱신합니다.
    """
    global action_text
    
    if motor_index is not None:
        min_val, max_val = motor_ranges[motor_index]
        
        # 1. 목표 위치 변경 및 범위 제한
        if direction == "increase":
            # 증가: 최대값을 넘지 않도록 제한
            motor_targets[motor_index] = min(max_val, motor_targets[motor_index] + step_size)
            action_text = f"Motor {motor_index + 1} ({motor_names[motor_index]}): +{step_size} → {int(motor_targets[motor_index])}"
        elif direction == "decrease":
            # 감소: 최소값을 넘지 않도록 제한
            motor_targets[motor_index] = max(min_val, motor_targets[motor_index] - step_size)
            action_text = f"Motor {motor_index + 1} ({motor_names[motor_index]}): -{step_size} → {int(motor_targets[motor_index])}"
        
        # 2. 목표가 변경될 때마다 명령 전송
        send_command()
    else:
        # 단순 상태 메시지 업데이트 (예: System Ready, Shutdown)
        action_text = action
        
    print(f"COMMAND: {action_text}")

# --- [6. 메인 루프 및 이벤트 처리] ---

clock = pygame.time.Clock() 
running = True

# 키보드 키와 모터 제어 동작을 매핑
key_mapping = {
    pygame.K_q: (0, "increase"),    # Q: M1 증가 (Base)
    pygame.K_a: (0, "decrease"),    # A: M1 감소
    pygame.K_w: (1, "increase"),    # W: M2 증가 (Shoulder)
    pygame.K_s: (1, "decrease"),    # S: M2 감소
    pygame.K_e: (2, "increase"),    # E: M3 증가 (Apear_Arm)
    pygame.K_d: (2, "decrease"),    # D: M3 감소
    pygame.K_r: (3, "increase"),    # R: M4 증가 (Elbow)
    pygame.K_f: (3, "decrease"),    # F: M4 감소

    pygame.K_t: (4, "increase"),    # T: M5 증가 (Wrist)
    pygame.K_g: (4, "decrease"),    # G: M5 감소 
    pygame.K_y: (5, "increase"),    # Y: M6 증가 (Hand)
    pygame.K_h: (5, "decrease"),    # H: M6 감소 
}

FAST_STEP_SIZE = 3 # 키를 누를 때마다 목표 위치가 변하는 단위

while running:
    current_time = pygame.time.get_ticks()
    
    # 1. 이벤트 처리 루프 (키 입력, 창 닫기 등)
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
            
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False
            elif event.key in key_mapping and event.key not in keys_pressed:
                # 키가 처음 눌렸을 때만 실행 (반복 방지)
                motor_index, direction = key_mapping[event.key]
                
                keys_pressed[event.key] = True # 눌린 상태로 기록
                
                # 키를 누른 순간 FAST_STEP_SIZE 만큼 위치 변경 및 명령 전송
                update_robot_action(f"Motor {motor_index + 1}", motor_index, direction, FAST_STEP_SIZE)
                
                # 키 반복 시작 시간을 설정 (딜레이 후 반복 시작)
                last_command_time[event.key] = current_time + KEY_REPEAT_DELAY
            
        if event.type == pygame.KEYUP:
            # 키에서 손을 뗄 때, 눌린 상태 기록 삭제
            if event.key in keys_pressed:
                del keys_pressed[event.key]
            if event.key in last_command_time:
                del last_command_time[event.key]
    
    # 2. 키 반복 처리 루프
    for key in list(keys_pressed.keys()):
        if key in key_mapping:
            # 반복 간격 시간이 지났으면
            if current_time >= last_command_time.get(key, 0): 
                motor_index, direction = key_mapping[key]
                
                # 명령 반복 전송 (FAST_STEP_SIZE 만큼 위치 변경)
                update_robot_action(f"Motor {motor_index + 1}", motor_index, direction, FAST_STEP_SIZE)
                
                # 다음 반복 명령 시간을 설정 (일정 간격)
                last_command_time[key] = current_time + KEY_REPEAT_INTERVAL

    # 3. 모터 상태 시뮬레이션 업데이트
    update_motor_angles()

    # 4. 화면 그리기
    draw_gradient_background()
    
    # 헤더 및 부제 그리기
    header_text = font_title.render("Manipulator Robot", True, TEXT_DARK)
    screen.blit(header_text, (30, 25))
    
    subtitle_text = font_tiny.render("Real-time Motor Dashboard (6-DOF)", True, TEXT_GRAY)
    screen.blit(subtitle_text, (30, 50))
    
    # 6개 모터 게이지 배치 및 그리기
    gauge_width = 410
    gauge_height = 110
    spacing = 25
    start_x = 30
    start_y = 85
    
    # **수정: range(6)으로 변경하여 6개 게이지 모두 그리기**
    for i in range(len(motor_targets)): 
        row = i // 2 # 0, 0, 1, 1, 2, 2 (총 3줄)
        col = i % 2  # 0, 1, 0, 1, 0, 1 (2열)
        x = start_x + col * (gauge_width + spacing)
        y = start_y + row * (gauge_height + spacing)
        draw_motor_gauge(x, y, gauge_width, gauge_height, i)
    
    draw_control_panel()
    
    # 최종 화면 업데이트
    pygame.display.flip()
    clock.tick(60) # 프레임 속도를 60 FPS로 제한

# --- [7. 종료 처리] ---
update_robot_action("System Shutdown", None, None)
print("Closing serial connection...")
# try/except로 직렬 포트 닫기 (연결에 실패했을 경우 오류 방지)
try:
    arduino.close() 
    print("Serial connection closed.")
except:
    print("Serial port was not open or already closed.")

pygame.quit()   # Pygame 모듈 종료
sys.exit()      # 프로그램 종료
