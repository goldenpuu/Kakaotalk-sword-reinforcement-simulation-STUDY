import pytesseract
import pyautogui
import cv2
import numpy as np
import re
import csv
import os
import time
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Tesseract 경로 (본인 경로 확인)
pytesseract.pytesseract.tesseract_cmd = r'D:\Program Files\Tesseract-OCR\tesseract.exe'

def capture_and_ocr(x, y, width, height):
    screenshot = pyautogui.screenshot(region=(x, y, width, height))
    
    # 1. OpenCV 이미지로 변환
    img = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
    
    # 2. 이미지 크기 확대 (핵심: 2배 또는 3배로 확대하면 OCR이 훨씬 잘 읽습니다)
    img = cv2.resize(img, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    
    # 3. 흑백 전환 및 이진화
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # 배경이 밝은 경우(기본 테마) 이진화 처리
    gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
    
    # 4. Tesseract 실행 (설정 추가: --psm 6는 단일 텍스트 블록으로 취급)
    custom_config = r'--psm 6'
    text = pytesseract.image_to_string(gray, lang='kor+eng', config=custom_config)
    return text

def extract_data(text):
    # search 대신 findall을 사용하여 화면 내의 모든 골드/레벨 정보를 찾습니다.
    gold_matches = re.findall(r'(?:남은|보유|사용)\s*골드\s*[:：]\s*([\d,.]+)', text)
    level_matches = re.findall(r'\+(\d+)', text)
    
    gold = 0
    # 가장 마지막(최신) 메시지의 데이터를 가져옵니다.
    if gold_matches:
        raw_gold = gold_matches[-1].replace(',', '').replace('.', '')
        if raw_gold.endswith('6') and len(raw_gold) > 3:
            raw_gold = raw_gold[:-1]
        if raw_gold:
            gold = int(raw_gold)
            
    level = int(level_matches[-1]) if level_matches else 0
    return gold, level

def check_status(text):
    # 전체 텍스트에서 가장 마지막에 나타난 상태 키워드를 확인합니다.
    # 부족/모으고 라는 단어가 포함된 마지막 줄을 찾는 방식이 안전합니다.
    lines = text.split('\n')
    for line in reversed(lines): # 아래에서 위로 검색
        if "부족" in line or "모으고" in line:
            return "GOLD_INSUFFICIENT"
    return "NORMAL"

# --- 추가된 CSV 저장 함수 ---
def save_log(level, gold, result):
    filename = 'reinforce_data.csv'
    header = ['timestamp', 'level', 'gold', 'result']
    file_exists = os.path.isfile(filename)
    
    with open(filename, 'a', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=header)
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'level': level,
            'gold': gold,
            'result': result
        })

def click_button_image(image_filename, confidence=0.9, search_region=None):
    full_path = os.path.join(BASE_DIR, image_filename)
    
    if not os.path.exists(full_path):
        return False
        
    try:
        # 한글 경로 대응을 위한 로드
        img_array = np.fromfile(full_path, np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        
        # locateAllOnScreen으로 화면의 모든 해당 버튼을 찾습니다.
        locations = list(pyautogui.locateAllOnScreen(img, confidence=confidence, region=search_region))
        
        if locations:
            # Y 좌표가 가장 큰(가장 아래에 있는) 버튼을 선택합니다.
            latest_button = max(locations, key=lambda l: l.top)
            
            # 버튼의 중앙 좌표를 계산해 클릭합니다.
            center_x = latest_button.left + latest_button.width / 2
            center_y = latest_button.top + latest_button.height / 2
            pyautogui.click(center_x, center_y)
            return True
            
        return False
    except Exception as e:
        return False

# --- 메인 실행 로직 ---
# OCR을 위한 전체 채팅 영역
target_region = (964, 1, 900, 1030) 

# 버튼 클릭을 위한 하단 영역 (최신 메시지 위주 - 예시 좌표이므로 본인 화면에 맞게 조정 필요)
# 전체 높이의 아래쪽 30%만 보도록 설정
click_search_region = (964, 600, 900, 430)

try:
    while True:
        raw_text = capture_and_ocr(*target_region)
        current_gold, current_level = extract_data(raw_text)
        status = check_status(raw_text)
        
        if status == "GOLD_INSUFFICIENT":
            # click_search_region 내에서만 '판매' 버튼을 찾습니다.
            if click_button_image('btn_sell.png', search_region=click_search_region):
                print(" -> [최신 메시지] 판매 버튼 클릭 성공")
                time.sleep(2)
        
        else:
            # 강화 로직 등...
            if current_level < 10:
                click_button_image('btn_reinforce.png', search_region=click_search_region)
                time.sleep(3)

        time.sleep(2)

except KeyboardInterrupt:
    print("\n감지를 종료합니다.")