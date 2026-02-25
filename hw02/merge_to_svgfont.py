import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
import statistics

def is_fullwidth(codepoint: int) -> bool:
    """判斷 Unicode 碼位是否為全形字元（CJK、假名、注音、全形符號等）"""
    return (
        0x1100 <= codepoint <= 0x115F or   # Hangul Jamo
        0x2E80 <= codepoint <= 0x2EFF or   # CJK 部首補充
        0x2F00 <= codepoint <= 0x2FDF or   # 康熙部首
        0x2FF0 <= codepoint <= 0x2FFF or   # 表意文字描述字符
        0x3000 <= codepoint <= 0x303F or   # CJK 標點符號
        0x3040 <= codepoint <= 0x309F or   # 平假名
        0x30A0 <= codepoint <= 0x30FF or   # 片假名
        0x3100 <= codepoint <= 0x312F or   # 注音符號
        0x3130 <= codepoint <= 0x318F or   # 韓文相容字母
        0x3190 <= codepoint <= 0x319F or   # 漢文訓讀
        0x31A0 <= codepoint <= 0x31BF or   # 注音符號（閩南語、客家語）
        0x31F0 <= codepoint <= 0x31FF or   # 片假名語音擴展
        0x3200 <= codepoint <= 0x32FF or   # 括號 CJK 字母與月份
        0x3300 <= codepoint <= 0x33FF or   # CJK 相容字符
        0x3400 <= codepoint <= 0x4DBF or   # CJK 擴展 A
        0x4E00 <= codepoint <= 0x9FFF or   # CJK 統一漢字
        0xA000 <= codepoint <= 0xA4CF or   # 彝文音節
        0xAC00 <= codepoint <= 0xD7AF or   # 韓文音節
        0xF900 <= codepoint <= 0xFAFF or   # CJK 相容表意字
        0xFE10 <= codepoint <= 0xFE1F or   # 直排標點
        0xFE30 <= codepoint <= 0xFE4F or   # CJK 相容形式
        0xFE50 <= codepoint <= 0xFE6F or   # 小寫變體
        0xFF01 <= codepoint <= 0xFF60 or   # 全形 ASCII 與半形片假名（全形部分）
        0xFFE0 <= codepoint <= 0xFFE6       # 全形符號
    )

def calculate_bounding_box(tokens):
    """計算路徑的邊界框"""
    min_x = float('inf')
    max_x = float('-inf')
    min_y = float('inf')
    max_y = float('-inf')
    
    is_x = True
    for cmd, val in tokens:
        if not cmd and val:
            num = float(val)
            if is_x:
                min_x = min(min_x, num)
                max_x = max(max_x, num)
                is_x = False
            else:
                min_y = min(min_y, num)
                max_y = max(max_y, num)
                is_x = True
        elif cmd:
            is_x = True
    
    if min_x == float('inf'):
        return None, None, None, None
    return min_x, max_x, min_y, max_y

def transform_tokens(tokens, global_origin_x, global_origin_y, uniform_square, canvas_size):
    """
    用全局基準偏移，統一縮放，翻轉 Y — 所有字形共用同一個變換，保留相對位置
    """
    scale = canvas_size / uniform_square
    
    new_tokens = []
    is_x = True
    
    for cmd, val in tokens:
        if cmd:
            new_tokens.append(cmd)
            is_x = True
        elif val:
            num = float(val)
            if is_x:
                x_val = (num - global_origin_x) * scale
                new_tokens.append(format(x_val, '.2f'))
                is_x = False
            else:
                y_val = (num - global_origin_y) * scale
                flipped_y = canvas_size - y_val
                new_tokens.append(format(flipped_y, '.2f'))
                is_x = True
    
    return new_tokens

def transform_tokens_with_shift(tokens, global_origin_x, global_origin_y, uniform_square, canvas_size, shift_x, shift_y, glyph_scale=1.0):
    """
    和 transform_tokens 相同，但額外加上偏移量，讓超出邊界的字移回來。
    glyph_scale < 1 時可等比縮小字形以適應目標寬度。
    """
    scale = canvas_size / uniform_square
    
    new_tokens = []
    is_x = True
    
    for cmd, val in tokens:
        if cmd:
            new_tokens.append(cmd)
            is_x = True
        elif val:
            num = float(val)
            if is_x:
                x_val = (num - global_origin_x) * scale * glyph_scale + shift_x
                new_tokens.append(format(x_val, '.2f'))
                is_x = False
            else:
                y_val = (num - global_origin_y) * scale * glyph_scale
                flipped_y = canvas_size - y_val + shift_y
                new_tokens.append(format(flipped_y, '.2f'))
                is_x = True
    
    return new_tokens

def create_svg_font_with_flip():
    font_name = 'MyFont'
    input_folder = Path('my_output_folder')
    output_dir = Path('final_font')
    output_path = output_dir / 'fontpico_py2.svg'
    
    output_dir.mkdir(parents=True, exist_ok=True)

    svg_header = f'''<?xml version="1.0" standalone="no"?>
<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" "http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd" >
<svg xmlns="http://www.w3.org/2000/svg">
<defs>
  <font id="{font_name}" horiz-adv-x="300">
    <font-face font-family="{font_name}"
      units-per-em="300" ascent="300"
      descent="0" />
    <missing-glyph horiz-adv-x="0" />
'''
    
    svg_files = sorted(list(input_folder.glob("*.svg")))
    
    # 第一遍掃描：收集每個字形的 bounding box
    print("掃描所有 SVG...")
    all_min_x = []
    all_max_x = []
    all_min_y = []
    all_max_y = []
    
    for svg_path in svg_files:
        try:
            tree = ET.parse(svg_path)
            root = tree.getroot()
            ns = {'svg': 'http://www.w3.org/2000/svg'}
            paths = root.findall('.//svg:path', ns) or root.findall('.//path')
            raw_d = " ".join([p.attrib.get('d', '') for p in paths])
            
            if not raw_d:
                continue
            
            tokens = re.findall(r"([a-zA-Z])|([-+]?\d*\.\d+|\d+)", raw_d)
            min_x, max_x, min_y, max_y = calculate_bounding_box(tokens)
            
            if min_x is None:
                continue
            
            all_min_x.append(min_x)
            all_max_x.append(max_x)
            all_min_y.append(min_y)
            all_max_y.append(max_y)
            
        except Exception as e:
            pass
    
    # 用中位數取範圍，排除歪字的影響
    all_min_x.sort()
    all_max_x.sort()
    all_min_y.sort()
    all_max_y.sort()
    n = len(all_min_x)
    
    # 用 5th / 95th 百分位數，排除最極端的 5%
    lo = max(0, int(n * 0.05))
    hi = min(n - 1, int(n * 0.95))
    
    crop_min_x = all_min_x[lo]
    crop_max_x = all_max_x[hi]
    crop_min_y = all_min_y[lo]
    crop_max_y = all_max_y[hi]
    
    crop_width = crop_max_x - crop_min_x
    crop_height = crop_max_y - crop_min_y
    uniform_square = max(crop_width, crop_height)
    
    # 居中較短的那邊
    crop_center_x = (crop_min_x + crop_max_x) / 2
    crop_center_y = (crop_min_y + crop_max_y) / 2
    global_origin_x = crop_center_x - uniform_square / 2
    global_origin_y = crop_center_y - uniform_square / 2
    
    print(f"5%-95% 範圍: X=[{crop_min_x:.2f}, {crop_max_x:.2f}], Y=[{crop_min_y:.2f}, {crop_max_y:.2f}]")
    print(f"裁剪後寬={crop_width:.2f}, 高={crop_height:.2f}, 統一正方形邊長={uniform_square:.2f}")
    
    canvas_size = 300  # 放大到 300x300
    MARGIN = 15  # 每個字形左右各留的邊距（單位同 units-per-em）
    FULLWIDTH_ADV = 300   # 全形字（CJK、假名、注音等）推進寬度
    HALFWIDTH_ADV = 150   # 半形字（ASCII、拉丁字母等）推進寬度
    
    # 第二遍掃描：使用最小正方形處理所有 SVG
    print("處理 SVG 文件...")
    glyph_definitions = []

    for svg_path in svg_files:
        match = re.search(r'[Uu]\+([0-9A-Fa-f]+)', svg_path.name)
        if not match:
            continue
        
        hex_code = match.group(1).upper()
        codepoint = int(hex_code, 16)
        target_adv = FULLWIDTH_ADV if is_fullwidth(codepoint) else HALFWIDTH_ADV
        glyph_name = f"icon_{hex_code}"
        unicode_entity = f"&#x{hex_code};"
        
        try:
            tree = ET.parse(svg_path)
            root = tree.getroot()
            ns = {'svg': 'http://www.w3.org/2000/svg'}
            paths = root.findall('.//svg:path', ns) or root.findall('.//path')
            raw_d = " ".join([p.attrib.get('d', '') for p in paths])
            
            if not raw_d:
                continue

            tokens = re.findall(r"([a-zA-Z])|([-+]?\d*\.\d+|\d+)", raw_d)
            min_x, max_x, min_y, max_y = calculate_bounding_box(tokens)
            
            if min_x is None:
                continue
            
            # 先用全局變換計算這個字形變換後的邊界
            scale = canvas_size / uniform_square
            t_min_x = (min_x - global_origin_x) * scale
            t_max_x = (max_x - global_origin_x) * scale
            # 翻轉後 min/max 互換
            t_min_y = canvas_size - (max_y - global_origin_y) * scale
            t_max_y = canvas_size - (min_y - global_origin_y) * scale
            
            # 計算需要的偏移量，讓超出邊界的字移回來
            # 在 target_adv 寬度內水平置中（全形=300，半形=150）
            ink_width = t_max_x - t_min_x
            max_ink_w = target_adv - 2 * MARGIN

            # 若字形墨水寬度超出可用空間，等比縮小
            glyph_scale = 1.0
            if ink_width > max_ink_w and ink_width > 0:
                glyph_scale = max_ink_w / ink_width

            if glyph_scale < 1.0:
                # 縮小後同時水平與垂直置中
                t_center_x = (t_min_x + t_max_x) / 2
                t_center_y = (t_min_y + t_max_y) / 2
                shift_x = target_adv / 2 - t_center_x * glyph_scale
                shift_y = (canvas_size - t_center_y) * glyph_scale - canvas_size / 2
            else:
                # 原始邏輯：水平置中，垂直只修正超出邊界
                shift_x = (target_adv - ink_width) / 2 - t_min_x
                shift_y = 0
                if t_min_y < 0:
                    shift_y = -t_min_y  # 往下推
                elif t_max_y > canvas_size:
                    shift_y = canvas_size - t_max_y  # 往上推

            # 固定推進寬度（全形=300，半形=150）
            horiz_adv_x = target_adv

            transformed_tokens = transform_tokens_with_shift(
                tokens, global_origin_x, global_origin_y, uniform_square,
                canvas_size, shift_x, shift_y, glyph_scale
            )
            transformed_d = " ".join(transformed_tokens)

            # 產出 glyph 標籤
            glyph_def = f'    <glyph glyph-name="{glyph_name}"\n' \
                        f'      unicode="{unicode_entity}"\n' \
                        f'      horiz-adv-x="{horiz_adv_x:.0f}" d="{transformed_d}" />'
            glyph_definitions.append(glyph_def)
            
        except Exception as e:
            print(f"Failed to process {svg_path.name}: {e}")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(svg_header)
        f.write("\n".join(glyph_definitions))
        f.write('\n  </font>\n</defs>\n</svg>')

    print(f"SVG Font：{output_path}")

if __name__ == "__main__":
    create_svg_font_with_flip()