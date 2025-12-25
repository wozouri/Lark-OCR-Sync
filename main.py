import pyautogui
import time
import cv2
import numpy as np
from paddleocr import PaddleOCR
import json
import pygetwindow as gw
import mss
import re # 确保导入 re 模块

# 1. 初始化 OCR
ocr = PaddleOCR(use_textline_orientation=False, lang="ch")

# ================= 配置区 (请填入 calibration.py 生成的数据) =================
CONFIG = {
    # 请确保这里是你 calibration.py 跑出来的最新坐标！
    "start_x": 3562,   
    "start_y": 267,    
    "step_x": 49,
    "step_y": 38,
    "detail_region": (3490, 489, 336, 480), 
    "total_days": 31,
    "first_day_weekday": 1 
}
# ========================================================================

def capture_region_mss(x, y, w, h):
    with mss.mss() as sct:
        monitor = {"top": int(y), "left": int(x), "width": int(w), "height": int(h)}
        sct_img = sct.grab(monitor)
        img_np = np.array(sct_img)
        img_bgr = cv2.cvtColor(img_np, cv2.COLOR_BGRA2BGR)
        return img_bgr

def force_activate_feishu():
    try:
        windows = gw.getWindowsWithTitle('飞书')
        if not windows: windows = gw.getWindowsWithTitle('Lark')
        if windows:
            win = windows[0]
            if win.isMinimized: win.restore()
            win.activate()
            win.maximize()
            time.sleep(1)
            return True
    except:
        pass
    print("⚠️ 无法自动最大化窗口，请手动全屏飞书窗口！")
    time.sleep(3)
    return True

def get_day_coordinates(day, config):
    grid_index = day - 1 + config["first_day_weekday"]
    row = grid_index // 7
    col = grid_index % 7
    x = config["start_x"] + (col - config["first_day_weekday"]) * config["step_x"]
    y = config["start_y"] + row * config["step_y"]
    return x, y

def run_fast_automation():
    force_activate_feishu()
    
    # === 阶段 1: 极速采集 ===
    print(f"🚀 [阶段 1/2] 正在极速采集 {CONFIG['total_days']} 天数据...")
    captured_data = [] 

    for day in range(1, CONFIG['total_days'] + 1):
        x, y = get_day_coordinates(day, CONFIG)
        pyautogui.click(x, y)
        time.sleep(0.25) # 稍微给点时间刷新
        
        dx, dy, dw, dh = CONFIG["detail_region"]
        img_np = capture_region_mss(dx, dy, dw, dh)
        
        captured_data.append({"day": day, "image": img_np})
        print(f"  📸 已采集: {day}日", end="\r")

    print("\n✅ 采集完成！开始后台识别...")

    # === 阶段 2: 后台计算 ===
    print(f"🐢 [阶段 2/2] 正在进行 OCR 识别与精准解析...")
    results = []
    
    for item in captured_data:
        day = item['day']
        img_np = item['image']
        
        # 图像处理：简单放大 2 倍
        img_gray = cv2.cvtColor(img_np, cv2.COLOR_BGR2GRAY)
        scale = 2.0 
        img_zoom = cv2.resize(img_gray, None, fx=scale, fy=scale)
        img_input = cv2.cvtColor(img_zoom, cv2.COLOR_GRAY2BGR)

        # OCR 推理
        ocr_result = ocr.ocr(img_input)

        daily_info = {
            "date": f"2025-12-{day}",
            "check_in": "",
            "check_out": "",
            "raw_text": []
        }

        if ocr_result and len(ocr_result) > 0:
            result_item = ocr_result[0]
            texts = []
            
            # 兼容性处理
            if isinstance(result_item, dict) and 'rec_texts' in result_item:
                texts = result_item['rec_texts']
            elif isinstance(result_item, list):
                texts = [line[1][0] for line in result_item]
            
            daily_info["raw_text"] = texts
            
            # =========== 🔥 核心修复逻辑开始 🔥 ===========
            valid_punches = []
            
            # 遍历每一行文字，只有包含“已打卡”的行，才提取时间
            for text_line in texts:
                if "已打卡" in text_line:
                    # 在这一行里找时间 (HH:MM)
                    found_times = re.findall(r"(\d{1,2}:\d{2})", text_line)
                    if found_times:
                        # 找到的时间加入列表
                        valid_punches.extend(found_times)
            
            # 过滤掉不合理的时间（比如 > 24:00）
            cleaned_punches = []
            for t in valid_punches:
                try:
                    h, m = map(int, t.split(':'))
                    if h < 24 and m < 60:
                        cleaned_punches.append(t)
                except: continue

            # 赋值：第一个是上班，最后一个是下班
            if cleaned_punches:
                daily_info["check_in"] = cleaned_punches[0]
                # 只有当打卡记录多于1条，且不相同时，才记录下班
                if len(cleaned_punches) > 1 and cleaned_punches[-1] != cleaned_punches[0]:
                    daily_info["check_out"] = cleaned_punches[-1]
            
            # 调试打印，方便你看结果
            print(f"✅ {day}日: 上班[{daily_info['check_in']}] 下班[{daily_info['check_out']}] | 原始内容: {texts}")
            # =========== 🔥 核心修复逻辑结束 🔥 ===========
        
        results.append(daily_info)

    # 导出结果
    output_file = "monthly_attendance.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"✅ 全部完成！数据已保存至 {output_file}")

if __name__ == "__main__":
    run_fast_automation()