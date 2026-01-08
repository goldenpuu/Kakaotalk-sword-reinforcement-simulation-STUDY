import pytesseract
import pyautogui
import cv2
import numpy as np
import re
import csv
import os
import time
from datetime import datetime
from collections import Counter, defaultdict

# --- [사용자 설정 구간] ---
TARGET_LEVEL = 12        # 🎯 목표 수치 도달 시 즉시 정지
RUN_TIME_MINUTES = 60    # ⏳ 매크로 총 작동 시간 (분 단위)
DASHBOARD_INTERVAL = 5   # 📊 대시보드 갱신 주기 (강화 시도 횟수 단위)
# -----------------------

# 경로 설정: 상위 폴더에 CSV 저장
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(BASE_DIR)
CSV_PATH = os.path.join(PARENT_DIR, 'reinforce_data.csv')

# Tesseract 경로 설정
pytesseract.pytesseract.tesseract_cmd = r'D:\Program Files\Tesseract-OCR\tesseract.exe'

def display_dashboard():
    """CSV를 읽어 통계를 출력합니다 (KeyError 방지 로직 적용)."""
    if not os.path.exists(CSV_PATH): return
    stats = defaultdict(list)
    try:
        with open(CSV_PATH, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                lv = row.get('base_level') or row.get('level')
                outcome = row.get('outcome') or row.get('result')
                if lv and outcome:
                    stats[lv].append(outcome)
        
        if not stats: return
        print("\n" + "="*70)
        print(f"{'Lv':<5} | {'시도':<6} | {'성공':<9} | {'유지':<9} | {'실패':<9} | {'파괴':<9}")
        print("-" * 70)
        for lv in sorted(stats.keys(), key=int):
            outcomes = Counter(stats[lv])
            total = sum(outcomes.values())
            print(f" +{lv:<3} | {total:<6} | "
                  f"{(outcomes.get('SUCCESS',0)/total)*100:>7.1f}% | "
                  f"{(outcomes.get('STAY',0)/total)*100:>7.1f}% | "
                  f"{(outcomes.get('FAIL',0)/total)*100:>7.1f}% | "
                  f"{(outcomes.get('DESTROYED',0)/total)*100:>7.1f}%")
        print("="*70 + "\n")
    except Exception as e:
        print(f"\n[대시보드 에러] {e}")

def capture_and_ocr(x, y, width, height):
    """이미지 전처리 후 OCR 수행"""
    screenshot = pyautogui.screenshot(region=(x, y, width, height))
    img = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
    img = cv2.resize(img, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
    return pytesseract.image_to_string(gray, lang='kor+eng', config='--psm 6')

def extract_data(text):
    """'강화 파괴' 키워드와 레벨을 정밀하게 추출합니다."""
    gold_matches = re.findall(r'(?:남은|보유|사용)\s*골드\s*[:：]\s*([\d,.]+)', text)
    level_matches = re.findall(r'\+(\d+)', text)
    
    gold = 0
    if gold_matches:
        raw_gold = re.sub(r'[^0-9]', '', gold_matches[-1])
        if raw_gold.endswith('6') and len(raw_gold) > 3: raw_gold = raw_gold[:-1]
        gold = int(raw_gold) if raw_gold else 0
            
    # 파괴 시 [+10]과 [+0]이 같이 보이므로 가장 마지막(최신) 레벨을 가져옵니다.
    level = int(level_matches[-1]) if level_matches else 0
    
    # [핵심] 사용자가 강조한 '강화 파괴' 키워드 탐지
    is_destroyed_msg = "강화 파괴" in text or "산산조각" in text
    is_stay_msg = "유지" in text
    
    return gold, level, is_stay_msg, is_destroyed_msg

def check_status(text):
    """골드 부족 상태를 확인합니다 (NameError 방지)."""
    lines = text.split('\n')
    for line in reversed(lines):
        if "부족" in line or "모으고" in line:
            return "GOLD_INSUFFICIENT"
    return "NORMAL"

def save_ai_log(base_level, result_level, outcome):
    """결과 로그 저장"""
    header = ['timestamp', 'base_level', 'result_level', 'outcome']
    file_exists = os.path.isfile(CSV_PATH)
    with open(CSV_PATH, 'a', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=header)
        if not file_exists: writer.writeheader()
        writer.writerow({
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'base_level': base_level, 'result_level': result_level, 'outcome': outcome
        })

def click_button_image(image_filename, confidence=0.85, search_region=None):
    """이미지 클릭 수행"""
    full_path = os.path.join(BASE_DIR, image_filename)
    if not os.path.exists(full_path): return False
    try:
        img_array = np.fromfile(full_path, np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        locations = list(pyautogui.locateAllOnScreen(img, confidence=confidence, region=search_region))
        if locations:
            latest = max(locations, key=lambda l: l.top)
            pyautogui.click(latest.left + latest.width/2, latest.top + latest.height/2)
            return True
        return False
    except: return False

# --- 메인 실행 로직 ---
target_region = (964, 1, 900, 1030)
click_region = (964, 500, 900, 480) # 속보를 피하기 위한 상향 조정
start_time = time.time()
end_time = start_time + (RUN_TIME_MINUTES * 60)
try_count = 0
prev_level = None

print(f"🚀 매크로 기동! (목표: +{TARGET_LEVEL}강 / 로그 위치: {CSV_PATH})")

try:
    while time.time() < end_time:
        # 남은 시간 실시간 안내 (사용자 설정 반영)
        remaining = int(end_time - time.time())
        rem_min, rem_sec = divmod(remaining, 60)
        print(f"\r⏳ [종료까지 남은 시간: {rem_min:02d}:{rem_sec:02d}] 상태 감지 중...", end="", flush=True)

        raw_text = capture_and_ocr(*target_region)
        current_gold, current_level, is_stay, is_destroyed = extract_data(raw_text)
        status = check_status(raw_text)

        # 1. 목표 달성 시 정지
        if current_level >= TARGET_LEVEL:
            print(f"\n\n✨ [목표 달성] +{current_level}강 달성! 매크로를 안전하게 종료합니다.")
            break

        # 2. 결과 판별 및 로그 기록 (중복 방지 로직)
        if prev_level is not None:
            outcome = None
            
            # 파괴 판별: '강화 파괴' 문구가 있고 이전 레벨이 0보다 컸을 때 1회만 기록
            if is_destroyed and prev_level > 0:
                outcome = "DESTROYED"
                print(f"\n[DESTROYED] +{prev_level} -> +0")
                save_ai_log(prev_level, 0, outcome)
                prev_level = 0 # 파괴되었으므로 즉시 0으로 리셋하여 +0 -> +0 방지
            
            # 파괴 상태가 아닐 때의 성공/실패/유지 판별
            elif not is_destroyed:
                if current_level > prev_level: 
                    outcome = "SUCCESS"
                elif current_level < prev_level and current_level > 0:
                    outcome = "FAIL"
                elif is_stay and current_level == prev_level and current_level > 0:
                    outcome = "STAY"
                
                if outcome:
                    print(f"\n[{outcome}] +{prev_level} -> +{current_level}")
                    save_ai_log(prev_level, current_level, outcome)
                    prev_level = current_level
            
            if outcome:
                try_count += 1
                if try_count % DASHBOARD_INTERVAL == 0: display_dashboard()
        else:
            prev_level = current_level

        # 3. 행동 로직
        if status == "GOLD_INSUFFICIENT":
            click_button_image('btn_sell.png', search_region=click_region)
            time.sleep(2)
        else:
            # 파괴되어 '묵념'이 떠도 그 위의 이전 '강화' 버튼을 눌러 다음 강화를 진행
            if click_button_image('btn_reinforce.png', search_region=click_region):
                time.sleep(3) # 애니메이션 대기
        time.sleep(1)

    display_dashboard()

except KeyboardInterrupt:
    print("\n\n🛑 사용자가 매크로를 중단했습니다.")
    display_dashboard()