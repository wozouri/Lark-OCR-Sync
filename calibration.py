import pyautogui
import time

def get_point(prompt):
    print(f"\n👉 {prompt}")
    input("   (移动鼠标到目标位置后，按【回车键】确认...)")
    x, y = pyautogui.position()
    print(f"   ✅ 已记录坐标: ({x}, {y})")
    return x, y

def run_calibration():
    print("==================================================")
    print("       飞书考勤助手 - 全自动校准工具 (智能版)")
    print("==================================================")
    print("⚠️  请务必先将飞书窗口【最大化】，确保坐标统一！")
    
    # --- 校准标题区域 ---
    print("\n--- 第零步：确定顶部【年月标题】位置 ---")
    print("   目标：左上角的日期文字，例如 '2026年1月'")
    hx1, hy1 = get_point("请点击【年份月份标题】的【左上角】")
    hx2, hy2 = get_point("请点击【年份月份标题】的【右下角】")
    header_w = abs(hx2 - hx1)
    header_h = abs(hy2 - hy1)

    # --- 原有步骤 ---
    print("\n--- 第一步：确定水平网格结构 ---")
    left_x, left_y = get_point("请点击日历任意一行【最左侧一格】(周日) 的中心")
    right_x, right_y = get_point("请点击【同一行】的【最右侧一格】(周六) 的中心")
    
    grid_width = abs(right_x - left_x)
    step_x = grid_width / 6  
    
    print("\n--- 第二步：确定垂直间距 ---")
    next_row_x, next_row_y = get_point("请点击【下一行】的【最左侧一格】(周日) 的中心")
    step_y = abs(next_row_y - left_y)

    print("\n--- 第三步：确定起始日期 ---")
    start_x, start_y = get_point("请点击日历上【1号】数字的中心位置")
    
    distance_from_left = start_x - left_x
    first_day_weekday = round(distance_from_left / step_x)
    
    print("\n--- 第四步：确定底部详情区范围 ---")
    dx1, dy1 = get_point("请点击【详情区域】的【左上角】 (包含'应上班'等文字)")
    dx2, dy2 = get_point("请点击【详情区域】的【右下角】")
    
    detail_w = abs(dx2 - dx1)
    detail_h = abs(dy2 - dy1)
    
    print("\n\n" + "="*50)
    print("🎉 校准完成！请复制以下内容覆盖 main.py 的 CONFIG：")
    print("="*50)
    print(f"""
CONFIG = {{
    "header_region": ({min(hx1, hx2)}, {min(hy1, hy2)}, {header_w}, {header_h}), 
    "start_x": {start_x},
    "start_y": {start_y},
    "step_x": {step_x:.2f},
    "step_y": {step_y},
    "detail_region": ({min(dx1, dx2)}, {min(dy1, dy2)}, {detail_w}, {detail_h}),
    "total_days": 31,                
    "first_day_weekday": {first_day_weekday} 
}}
""")
    print("="*50)

if __name__ == "__main__":
    run_calibration()