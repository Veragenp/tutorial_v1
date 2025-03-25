import cv2
import pytesseract
import numpy as np

# Указываем путь к исполняемому файлу Tesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Загружаем изображение
image = cv2.imread("src/chart.jpg")
if image is None:
    print("Ошибка: изображение не загружено. Проверь путь к файлу!")
    exit()

# Преобразуем изображение в HSV
hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

# Определяем диапазоны цветов
colors = {
    "pink":  [(140, 50, 50), (180, 255, 255)],  # Розовый
    "blue":  [(100, 50, 50), (130, 255, 255)],  # Синий
    "cyan":  [(80, 50, 50), (99, 255, 255)]     # Голубой
}

recognized_texts = []

for color_name, (lower, upper) in colors.items():
    lower_bound = np.array(lower, dtype=np.uint8)
    upper_bound = np.array(upper, dtype=np.uint8)
    mask = cv2.inRange(hsv, lower_bound, upper_bound)
    
    # Ищем контуры текста в выбранных цветах
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        roi = image[y:y+h, x:x+w]
        
        # Преобразуем ROI в серый цвет перед распознаванием
        roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        
        # Распознаем текст
        text = pytesseract.image_to_string(roi_gray, config="--psm 6").strip()
        if text:
            recognized_texts.append(text)
            print(f"Распознанный уровень ({color_name}): {text}")
