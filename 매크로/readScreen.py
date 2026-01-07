import pytesseract
import pyautogui
import cv2
import numpy as np
import re
from PIL import Image

# 1. Tesseract 설치 경로 설정 (본인의 설치 경로로 수정 필수)
pytesseract.pytesseract.tesseract_cmd = r'D:\Program Files\Tesseract-OCR\tesseract.exe'

def capture_and_ocr(x, y, width, height):
    # 2. 지정한 영역 화면 캡처
    screenshot = pyautogui.screenshot(region=(x, y, width, height))
    
    # 3. 이미지 전처리 (OCR 인식률 향상)
    # OpenCV를 사용하기 위해 numpy 배열로 변환
    img = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) # 흑백 전환
    
    # 노이즈 제거 및 이진화 (글자를 더 선명하게)
    gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]

    # 4. OCR 실행 (한글+영어 학습 데이터 사용)
    text = pytesseract.image_to_string(gray, lang='kor+eng')
    return text

def extract_data(text):
    # 5. 정규표현식을 이용한 데이터 파싱
    # 예: "보유 골드: 577 G" 에서 숫자만 추출
    gold_match = re.search(r'보유\s*골드\s*:\s*([\d,]+)', text)
    level_match = re.search(r'\[\+(\d+)\]', text)
    
    gold = gold_match.group(1).replace(',', '') if gold_match else "N/A"
    level = level_match.group(1) if level_match else "N/A"
    
    return gold, level

# --- 메인 실행 로직 ---
# 실제 카카오톡 채팅창의 위치(x, y)와 크기(w, h)를 입력해야 합니다.
# 팁: pyautogui.mouseInfo()를 실행하면 현재 마우스 좌표를 쉽게 알 수 있습니다.
target_region = (964,1, 900, 1030) 

print("데이터 추출 시작...")
raw_text = capture_and_ocr(*target_region)
gold, level = extract_data(raw_text)

print(f"--- 추출 결과 ---")
print(f"전체 텍스트: \n{raw_text}")
print(f"파싱된 골드: {gold}")
print(f"파싱된 강화도: {level}")

#3. 코드 포인트 설명
#이미지 전처리 (cv2.threshold): 카카오톡 배경색이나 채팅방 테마에 따라 글자 인식이 안 될 수 있습니다. 이진화(Thresholding)를 거쳐 배경은 흰색, 글자는 검은색으로 만들면 인식률이 비약적으로 상승합니다.
#정규표현식 (re): 게임 메시지 특성상 공백이나 특수문자가 섞여 들어올 수 있습니다. \s* 등을 사용하여 유연하게 패턴을 매칭하는 것이 핵심입니다.
#좌표 설정: pyautogui.mouseInfo()를 호출하여 카카오톡 창의 좌측 상단과 우측 하단 좌표를 먼저 따내는 작업을 선행하시길 추천합니다.