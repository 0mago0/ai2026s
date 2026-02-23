import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path

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

def transform_tokens(tokens, global_min_x, global_min_y, uniform_square, canvas_size):
    """
    用全局基準偏移，統一縮放，翻轉 Y
    - global_min_x, global_min_y: 所有字形的全局最小值
    - uniform_square: 全局正方形邊長
    - canvas_size: 目標畫布大小 (300)
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
                # 用全局 min_x 偏移，再縮放
                x_val = (num - global_min_x) * scale
                new_tokens.append(format(x_val, '.2f'))
                is_x = False
            else:
                # 用全局 min_y 偏移，縮放，翻轉
                y_val = (num - global_min_y) * scale
                flipped_y = canvas_size - y_val
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
    
    # 第一遍掃描：計算所有字形的全局 bounding box
    print("掃描所有 SVG...")
    global_min_x = float('inf')
    global_max_x = float('-inf')
    global_min_y = float('inf')
    global_max_y = float('-inf')
    
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
            
            global_min_x = min(global_min_x, min_x)
            global_max_x = max(global_max_x, max_x)
            global_min_y = min(global_min_y, min_y)
            global_max_y = max(global_max_y, max_y)
            
        except Exception as e:
            pass
    
    # 用全局寬高的較大值作為統一正方形邊長
    global_width = global_max_x - global_min_x
    global_height = global_max_y - global_min_y
    uniform_square = max(global_width, global_height)
    print(f"全局範圍: X=[{global_min_x:.2f}, {global_max_x:.2f}], Y=[{global_min_y:.2f}, {global_max_y:.2f}]")
    print(f"全局寬={global_width:.2f}, 高={global_height:.2f}, 統一正方形邊長={uniform_square:.2f}")
    
    # 將全局基準調整為正方形（居中較短的那邊）
    if global_width > global_height:
        pad = (global_width - global_height) / 2
        global_min_y -= pad
    else:
        pad = (global_height - global_width) / 2
        global_min_x -= pad
    
    canvas_size = 300  # 放大到 300x300
    
    # 第二遍掃描：使用最小正方形處理所有 SVG
    print("處理 SVG 文件...")
    glyph_definitions = []

    for svg_path in svg_files:
        match = re.search(r'[Uu]\+([0-9A-Fa-f]+)', svg_path.name)
        if not match:
            continue
        
        hex_code = match.group(1).upper()
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
            
            # 用全局基準偏移，統一縮放，維持相對位置
            transformed_tokens = transform_tokens(tokens, global_min_x, global_min_y, uniform_square, canvas_size)
            transformed_d = " ".join(transformed_tokens)

            # 產出 glyph 標籤
            glyph_def = f'    <glyph glyph-name="{glyph_name}"\n' \
                        f'      unicode="{unicode_entity}"\n' \
                        f'      horiz-adv-x="300" d="{transformed_d}" />'
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