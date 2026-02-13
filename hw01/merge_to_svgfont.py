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

def scale_and_offset_tokens(tokens, scale, offset_x, offset_y, canvas_height):
    """縮放、偏移座標和翻轉 Y 軸"""
    new_tokens = []
    is_x = True
    
    for cmd, val in tokens:
        if cmd:
            new_tokens.append(cmd)
            is_x = True
        elif val:
            num = float(val)
            if is_x:
                # 縮放並偏移 X 座標
                scaled_x = num * scale + offset_x
                new_tokens.append(format(scaled_x, '.2f'))
                is_x = False
            else:
                # 縮放並偏移 Y 座標，然後翻轉
                scaled_y = num * scale + offset_y
                flipped_y = canvas_height - scaled_y
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
    
    glyph_definitions = []
    svg_files = sorted(list(input_folder.glob("*.svg")))

    # 翻轉參數：畫布高度為 300
    canvas_height = 300
    canvas_width = 300
    target_size_ratio = 0.8  # 文字占畫布的 80%

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

            # 正則表達式抓取指令(字母)與數字
            tokens = re.findall(r"([a-zA-Z])|([-+]?\d*\.\d+|\d+)", raw_d)
            
            # 計算邊界框
            min_x, max_x, min_y, max_y = calculate_bounding_box(tokens)
            
            if min_x is None:
                continue
            
            # 計算寬度和高度
            width = max_x - min_x
            height = max_y - min_y
            
            # 計算縮放因子，讓文字占畫布的 80%
            scale_x = (canvas_width * target_size_ratio) / width if width > 0 else 1
            scale_y = (canvas_height * target_size_ratio) / height if height > 0 else 1
            scale = min(scale_x, scale_y)  # 等比縮放
            
            # 計算縮放後的新尺寸
            new_width = width * scale
            new_height = height * scale
            
            # 計算偏移，使文字居中
            offset_x = (canvas_width - new_width) / 2 - min_x * scale
            offset_y = (canvas_height - new_height) / 2 - min_y * scale
            
            # 縮放、偏移和翻轉 Y 座標
            transformed_tokens = scale_and_offset_tokens(tokens, scale, offset_x, offset_y, canvas_height)
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