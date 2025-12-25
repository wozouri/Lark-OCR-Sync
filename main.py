import pyautogui
import time
import cv2
import numpy as np
from paddleocr import PaddleOCR
import json
import pygetwindow as gw
import mss  # 核心截图库

# 1. 初始化 OCR (去除不兼容参数)
# 首次运行会自动下载模型，请耐心等待
ocr = PaddleOCR(use_textline_orientation=False, lang="ch")

# ================= 配置区 (请填入 calibration.py 生成的数据) =================
CONFIG = {
    "start_x": 3562,
    "start_y": 267,
    "step_x": 49,
    "step_y": 38,

    # 详情区域 (x, y, w, h)
    "detail_region": (3490, 489, 336, 480),

    "total_days": 31,
    "first_day_weekday": 1
}

# ========================================================================

def capture_region_mss(x, y, w, h):
    """ 使用 MSS 进行跨屏幕截图，解决副屏黑屏问题 """
    with mss.mss() as sct:
        monitor = {"top": int(y), "left": int(x), "width": int(w), "height": int(h)}
        sct_img = sct.grab(monitor)
        img_np = np.array(sct_img)
        # MSS 返回 BGRA，OpenCV 需要 BGR
        img_bgr = cv2.cvtColor(img_np, cv2.COLOR_BGRA2BGR)
        return img_bgr

def force_activate_feishu():
    """ 强制激活窗口并最大化，保证坐标不偏移 """
    try:
        windows = gw.getWindowsWithTitle('飞书')
        if not windows: windows = gw.getWindowsWithTitle('Lark')
        if windows:
            win = windows[0]
            if win.isMinimized: win.restore()
            win.activate()
            win.maximize() # 强制全屏
            time.sleep(1)
            return True
    except:
        pass
    print("⚠️ 无法自动最大化窗口，请手动全屏飞书窗口！")
    time.sleep(3)
    return True

def get_day_coordinates(day, config):
    """ 计算每一天的点击坐标 """
    grid_index = day - 1 + config["first_day_weekday"]
    row = grid_index // 7
    col = grid_index % 7
    x = config["start_x"] + (col - config["first_day_weekday"]) * config["step_x"]
    y = config["start_y"] + row * config["step_y"]
    return x, y

def run_fast_automation():
    force_activate_feishu()
    
    # === 阶段 1: 极速采集 (只截图，不识别) ===
    print(f"🚀 [阶段 1/2] 正在极速采集 {CONFIG['total_days']} 天数据...")
    captured_data = [] 

    for day in range(1, CONFIG['total_days'] + 1):
        x, y = get_day_coordinates(day, CONFIG)
        
        # 1. 点击日期
        pyautogui.click(x, y)
        
        # 2. 极短等待 (0.2秒足够飞书刷新本地UI)
        time.sleep(0.2) 
        
        # 3. 截图存内存
        dx, dy, dw, dh = CONFIG["detail_region"]
        img_np = capture_region_mss(dx, dy, dw, dh)
        
        captured_data.append({"day": day, "image": img_np})
        print(f"  📸 已采集: {day}日", end="\r")

    print("\n✅ 采集完成！鼠标已释放，开始后台识别...")

    # === 阶段 2: 后台计算 (OCR 识别) ===
    print(f"🐢 [阶段 2/2] 正在进行 OCR 识别，请稍候...")
    results = []
    
    for item in captured_data:
        day = item['day']
        img_np = item['image']
        
        # 图像处理：简单放大 2 倍 (最稳妥方案)
        # 不做二值化，防止笔画粘连
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

        # 数据解析 (兼容 PaddleOCR 新版字典格式)
        if ocr_result and len(ocr_result) > 0:
            result_item = ocr_result[0]
            texts = []
            
            # 提取文字列表
            if isinstance(result_item, dict) and 'rec_texts' in result_item:
                texts = result_item['rec_texts']
            elif isinstance(result_item, list):
                texts = [line[1][0] for line in result_item]
            
            daily_info["raw_text"] = texts
            print(f"Processing {day}日: {texts}")

            # 提取 HH:MM 时间
            import re
            full_text = " ".join(texts)
            times = re.findall(r"(\d{1,2}:\d{2})", full_text)
            
            valid_times = []
            for t in times:
                try:
                    h, m = map(int, t.split(':'))
                    if h < 24 and m < 60: valid_times.append(t)
                except: continue

            if valid_times:
                daily_info["check_in"] = valid_times[0]
                if len(valid_times) > 1 and valid_times[-1] != valid_times[0]:
                    daily_info["check_out"] = valid_times[-1]
        
        results.append(daily_info)

    # 导出结果
    output_file = "monthly_attendance.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"✅ 全部完成！数据已保存至 {output_file}")

if __name__ == "__main__":
    run_fast_automation()