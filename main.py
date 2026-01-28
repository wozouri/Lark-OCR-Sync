import pyautogui
import time
import cv2
import numpy as np
from rapidocr_onnxruntime import RapidOCR
import json
import pygetwindow as gw
import mss
import re
import threading
import queue

# ================= 配置区 =================
CONFIG = {
    "header_region": (3487, 99, 95, 34),
    "start_x": 3710,
    "start_y": 267,
    "step_x": 49.50,
    "step_y": 38,
    "detail_region": (3489, 463, 338, 507),
    "total_days": 31,
    "first_day_weekday": 4
}
# =========================================

# 全局初始化 OCR (只加载一次，速度最快)
ocr_engine = RapidOCR(det_use_cuda=False, cls_use_cuda=False, rec_use_cuda=False)

# 创建一个队列，用于在“截图线程”和“识别线程”之间传图
task_queue = queue.Queue()
results_list = []

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
    except: pass
    print("⚠️ 无法自动最大化，请手动全屏飞书窗口！")
    time.sleep(3)
    return True

def identify_month_from_header(config):
    print("👀 正在识别当前月份...")
    x, y, w, h = config["header_region"]
    img_np = capture_region_mss(x, y, w, h)
    img_gray = cv2.cvtColor(img_np, cv2.COLOR_BGR2GRAY)
    img_zoom = cv2.resize(img_gray, None, fx=2.0, fy=2.0)
    
    result, _ = ocr_engine(img_zoom)
    
    if not result:
        return None

    all_text = "".join([line[1] for line in result])
    match = re.search(r"(\d{4})年(\d{1,2})月", all_text)
    if match:
        year = match.group(1)
        month = match.group(2).zfill(2)
        return f"{year}-{month}"
    return None

def get_day_coordinates(day, config):
    day_offset = day - 1
    current_grid_index = config["first_day_weekday"] + day_offset
    row_index = current_grid_index // 7
    col_index = current_grid_index % 7
    target_x = config["start_x"] + (col_index - config["first_day_weekday"]) * config["step_x"]
    target_y = config["start_y"] + row_index * config["step_y"]
    return int(target_x), int(target_y)

def ocr_worker_thread():
    """ 
    👷 后台消费者线程：
    时刻盯着队列，一旦有新截图送进来，马上识别。
    """
    while True:
        # 获取任务 (如果队列空了，这里会阻塞等待，不占CPU)
        item = task_queue.get()
        
        # 毒丸策略：如果收到 None，说明任务都结束了，下班
        if item is None:
            task_queue.task_done()
            break
            
        day = item['day']
        img_np = item['image']
        month_str = item['month_str']
        
        # --- 识别逻辑 ---
        # 预处理
        img_gray = cv2.cvtColor(img_np, cv2.COLOR_BGR2GRAY)
        img_zoom = cv2.resize(img_gray, None, fx=2.0, fy=2.0)
        
        # 执行 OCR (复用全局实例，极快)
        result, _ = ocr_engine(img_zoom)
        
        # 数据解析
        current_date_str = f"{month_str}-{day:02d}"
        daily_info = {
            "date": current_date_str,
            "check_in": "",
            "check_out": "",
            "raw_text": []
        }

        if result:
            texts = [line[1] for line in result]
            daily_info["raw_text"] = texts
            valid_punches = []
            for text_line in texts:
                clean_line = text_line.replace("：", ":").replace(" ", "")
                if "已打卡" in clean_line:
                    found_times = re.findall(r"(\d{1,2}:\d{2})", clean_line)
                    if found_times:
                        valid_punches.extend(found_times)
            
            cleaned_punches = []
            for t in valid_punches:
                try:
                    h, m = map(int, t.split(':'))
                    if 0 <= h < 24 and 0 <= m < 60:
                        cleaned_punches.append(t)
                except: continue
            cleaned_punches = sorted(list(set(cleaned_punches)))

            if cleaned_punches:
                daily_info["check_in"] = cleaned_punches[0]
                if len(cleaned_punches) > 1:
                    daily_info["check_out"] = cleaned_punches[-1]

        # 存入结果列表
        results_list.append(daily_info)
        
        # 打印进度 (实时反馈)
        print(f"  ⚡ 已识别 {current_date_str} | 上班:{daily_info['check_in'] or '--:--'} 下班:{daily_info['check_out'] or '--:--'}")
        
        # 标记此任务完成
        task_queue.task_done()

def run_fast_automation():
    if not force_activate_feishu():
        return

    # 1. 识别月份
    target_month = identify_month_from_header(CONFIG)
    if not target_month:
        target_month = input("请输入月份 (格式 YYYY-MM): ").strip()
    
    print(f"\n🚀 [流水线启动] 正在采集 {target_month} 数据...")
    print("💡 程序将【边截图，边识别】，请勿触碰鼠标...\n")
    
    # 2. 启动后台 OCR 线程
    worker = threading.Thread(target=ocr_worker_thread, daemon=True)
    worker.start()

    # 3. 主线程负责截图 (生产者)
    for day in range(1, CONFIG['total_days'] + 1):
        x, y = get_day_coordinates(day, CONFIG)
        pyautogui.click(x, y)
        time.sleep(0.35) # 等待UI刷新
        
        dx, dy, dw, dh = CONFIG["detail_region"]
        img_np = capture_region_mss(dx, dy, dw, dh)
        
        # 🔥 将截图扔进队列，后台线程马上就会处理它
        task_queue.put({
            "day": day,
            "image": img_np,
            "month_str": target_month
        })
        
        print(f"  📸 [{day:02d}/{CONFIG['total_days']}] 截图完成 -> 已送入识别队列", end="\r")

    # 4. 截图循环结束，发送结束信号
    print("\n\n✅ 所有截图已完成！正在等待最后几张识别结果...")
    task_queue.put(None) # 发送毒丸，通知线程结束
    
    # 等待队列清空
    worker.join()
    
    # 5. 排序并保存 (因为多线程处理顺序可能微小错乱，按日期排个序)
    results_list.sort(key=lambda x: x['date'])

    output_file = f"attendance_{target_month}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results_list, f, ensure_ascii=False, indent=2)
    print(f"\n🎉 全部完成！结果已保存至 {output_file}")

if __name__ == "__main__":
    run_fast_automation()