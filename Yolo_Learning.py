import cv2
import numpy as np
from ultralytics import YOLO
from collections import deque

# ================= КОНФИГУРАЦИЯ =================
TABLE_WIDTH_CM = 60.0 
TABLE_HEIGHT_CM = 45.0

# Путь только к модели ПРЕДМЕТА
MODEL_ITEM_PATH  = r"E:\dron\.venv\weigts\best (1) (1).pt" 

CONFIDENCE_ITEM = 0.5
# ================================================

class Smoother:
    """Сглаживает координаты (скользящее среднее)"""
    def __init__(self, buffer_size=5):
        self.buffer = deque(maxlen=buffer_size)
    
    def update(self, val):
        self.buffer.append(val)
        return sum(self.buffer) / len(self.buffer)

# Сглаживатели
smooth_x = Smoother(buffer_size=5)
smooth_y = Smoother(buffer_size=5)

# Глобальные переменные для кликов мыши
calibration_corners = []
is_calibrated = False

def mouse_callback(event, x, y, flags, param):
    """Обработка кликов для ручной настройки углов стола"""
    global calibration_corners, is_calibrated
    
    if event == cv2.EVENT_LBUTTONDOWN and not is_calibrated:
        if len(calibration_corners) < 4:
            calibration_corners.append((x, y))
            print(f"Точка {len(calibration_corners)}: {x}, {y}")

def order_points(pts):
    """Сортировка углов: TL, TR, BR, BL"""
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)] 
    rect[2] = pts[np.argmax(s)] 
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)] 
    rect[3] = pts[np.argmax(diff)] 
    return rect

def draw_grid_and_axes(img, matrix, w_cm, h_cm):
    """Рисует сетку поверх стола для наглядности"""
    try:
        _, inv_matrix = cv2.invert(matrix)
        
        # Рисуем сетку каждые 10 см
        for x in range(0, int(w_cm) + 1, 10):
            p1 = cv2.perspectiveTransform(np.array([[[x, 0]]], dtype=np.float32), inv_matrix)
            p2 = cv2.perspectiveTransform(np.array([[[x, h_cm]]], dtype=np.float32), inv_matrix)
            cv2.line(img, tuple(p1[0][0].astype(int)), tuple(p2[0][0].astype(int)), (0, 255, 255), 1)
        
        for y in range(0, int(h_cm) + 1, 10):
            p1 = cv2.perspectiveTransform(np.array([[[0, y]]], dtype=np.float32), inv_matrix)
            p2 = cv2.perspectiveTransform(np.array([[[w_cm, y]]], dtype=np.float32), inv_matrix)
            cv2.line(img, tuple(p1[0][0].astype(int)), tuple(p2[0][0].astype(int)), (0, 255, 255), 1)
            
        # Подписываем начало координат (0,0)
        origin = cv2.perspectiveTransform(np.array([[[0, 0]]], dtype=np.float32), inv_matrix)
        cv2.circle(img, tuple(origin[0][0].astype(int)), 5, (0, 0, 255), -1)
        
    except: pass

def main():
    global is_calibrated, calibration_corners
    
    print("--- ЗАГРУЗКА МОДЕЛИ ПРЕДМЕТА ---")
    try:
        net_item = YOLO(MODEL_ITEM_PATH)
    except Exception as e:
        print(f"Ошибка модели: {e}")
        return

    # Открываем камеру
    cap = cv2.VideoCapture(1, cv2.CAP_DSHOW) # Попробуй 0 или 1
    if not cap.isOpened():
        cap = cv2.VideoCapture(0)
    
    cap.set(3, 1280)
    cap.set(4, 720)

    # Окно и мышь
    cv2.namedWindow("Work Area")
    cv2.setMouseCallback("Work Area", mouse_callback)

    # Реальные размеры стола (для перспективы)
    real_corners = np.float32([
        [0, 0], 
        [TABLE_WIDTH_CM, 0], 
        [TABLE_WIDTH_CM, TABLE_HEIGHT_CM], 
        [0, TABLE_HEIGHT_CM]
    ])
    
    perspective_matrix = None

    print("\n=== ИНСТРУКЦИЯ ===")
    print("Кликните 4 угла стола в любом порядке.")
    print("Нажмите 'R' чтобы сбросить точки.")
    print("Нажмите 'Q' для выхода.\n")

    while True:
        ret, frame = cap.read()
        if not ret: break

        # 1. ЭТАП КАЛИБРОВКИ
        if not is_calibrated:
            cv2.putText(frame, f"Click Corners: {len(calibration_corners)}/4", (20, 40), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            
            # Рисуем кликнутые точки
            for pt in calibration_corners:
                cv2.circle(frame, pt, 5, (0, 255, 0), -1)

            # Если набрали 4 точки, считаем матрицу
            if len(calibration_corners) == 4:
                pts_src = np.array(calibration_corners, dtype="float32")
                pts_src = order_points(pts_src) # Упорядочиваем
                perspective_matrix = cv2.getPerspectiveTransform(pts_src, real_corners)
                is_calibrated = True
                print("Калибровка завершена! Начинаем поиск предметов.")

        # 2. ЭТАП РАБОТЫ (когда матрица уже есть)
        else:
            # Рисуем зону стола (полигон)
            if perspective_matrix is not None:
                # Рисуем сетку координат
                draw_grid_and_axes(frame, perspective_matrix, TABLE_WIDTH_CM, TABLE_HEIGHT_CM)
                
                # --- ПОИСК ПРЕДМЕТА (YOLO) ---
                results = net_item(frame, verbose=False, conf=CONFIDENCE_ITEM)[0]
                
                if results.boxes:
                    for i, box in enumerate(results.boxes):
                        # Получаем координаты бокса
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        
                        # Определяем центр предмета
                        # (Если модель умеет Keypoints - лучше использовать их, 
                        # если нет - берем центр бокса)
                        
                        cx, cy = 0, 0
                        has_keypoint = False

                        if results.keypoints is not None and len(results.keypoints.data) > i:
                            kpt = results.keypoints.data[i][0] # Берем первую точку
                            if kpt[2] > 0.5: # Если уверенность ок
                                cx, cy = int(kpt[0]), int(kpt[1])
                                has_keypoint = True
                        
                        # Если кейпоинтов нет, берем центр прямоугольника
                        if not has_keypoint:
                            cx = int((x1 + x2) / 2)
                            cy = int((y1 + y2) / 2)

                        # Рисуем сам предмет
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 100, 0), 2)
                        cv2.circle(frame, (cx, cy), 5, (0, 0, 255), -1)

                        # --- ПЕРЕВОД В СМ ---
                        vec = np.array([[[cx, cy]]], dtype=np.float32)
                        real_pt = cv2.perspectiveTransform(vec, perspective_matrix)
                        
                        raw_x = real_pt[0][0][0]
                        raw_y = real_pt[0][0][1]

                        # Сглаживание
                        val_x = smooth_x.update(raw_x)
                        val_y = smooth_y.update(raw_y)

                        # Проверка границ стола
                        in_bounds = (0 <= val_x <= TABLE_WIDTH_CM) and (0 <= val_y <= TABLE_HEIGHT_CM)
                        color_text = (0, 255, 0) if in_bounds else (0, 0, 255)

                        # Вывод текста
                        text = f"X:{val_x:.1f} Y:{val_y:.1f}"
                        cv2.putText(frame, text, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color_text, 2)

        # Управление клавишами
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'): break
        if key == ord('r'): # Сброс калибровки
            calibration_corners = []
            is_calibrated = False
            perspective_matrix = None
            print("Калибровка сброшена.")

        cv2.imshow("Work Area", frame)

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
