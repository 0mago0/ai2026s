#!/usr/bin/env python3
"""
將指定目錄中的 SVG 檔案複製並轉換檔名為 Unicode 格式 (U+XXXX.svg) 到目標資料夾
例如：A.svg -> unicode_svgs/U+0041.svg, 一.svg -> unicode_svgs/U+4E00.svg
usage: python3 rename_to_unicode.py [-i INPUT_DIR] [-o OUTPUT_DIR]
"""

import os
import re
import urllib.parse
import shutil
import argparse

def main():
    parser = argparse.ArgumentParser(description='將 SVG 檔案名稱轉換為 Unicode 格式並複製到新目錄')
    parser.add_argument('-i', '--input', default='.', help='輸入資料夾路徑 (預設: 當前目錄)')
    parser.add_argument('-o', '--output', default='unicode_svgs', help='輸出資料夾路徑 (預設: unicode_svgs)')
    args = parser.parse_args()

    input_dir = os.path.abspath(args.input)
    output_dir = os.path.abspath(args.output)

    if not os.path.exists(input_dir):
        print(f"錯誤: 輸入資料夾 '{input_dir}' 不存在")
        return

    # 如果目標資料夾不存在，則建立
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f'已建立目標資料夾: {output_dir}')
    else:
        print(f'目標資料夾已存在: {output_dir}')

    print(f"來源: {input_dir}")
    print(f"目標: {output_dir}")

    # 收集所有 .svg 檔案（僅掃描輸入目錄下的檔案，不包含子目錄）
    svg_files = [f for f in os.listdir(input_dir) 
                 if f.endswith('.svg') and os.path.isfile(os.path.join(input_dir, f))]
    svg_files.sort()

    processed = 0
    skipped = 0
    errors = []

    print(f"找到 {len(svg_files)} 個 SVG 檔案，準備處理...")

    for filename in svg_files:
        base = filename[:-4]  # 去掉 .svg

        # 這裡不跳過已經是 U+ 開頭的檔案，因為我們是要複製到新資料夾，
        # 如果使用者想要整理現有的檔案，照樣複製過去改名（如果需要的話）或者保持原名。
        # 但為了避免重複處理或混亂，我們還是重新計算一次標準的 Unicode 名稱。

        # 處理帶有 -N 後綴的檔案，例如 一-1.svg
        suffix = ''
        match = re.match(r'^(.+?)(-\d+)$', base)
        if match:
            char_part = match.group(1)
            suffix = match.group(2)
        else:
            char_part = base

        # 處理 URL 編碼的檔名（如 %22, %2A 等）
        try:
            decoded = urllib.parse.unquote(char_part)
        except Exception:
            decoded = char_part

        # 檢查 decoded string 是否看起來已經是 Unicode 格式 (例如 "U+4E00")
        if re.match(r'^U\+[0-9A-Fa-f]{4,}(?:_[Uu]\+[0-9A-Fa-f]{4,})*$', char_part):
            # 如果主要部分已經是 U+XXXX 格式，我們假設它是正確的，直接使用作為新檔名的一部分
            new_base = char_part + suffix
        else:
            # 將字元轉換為 U+XXXX 格式
            unicode_parts = []
            for ch in decoded:
                codepoint = ord(ch)
                if codepoint <= 0xFFFF:
                    unicode_parts.append(f'U+{codepoint:04X}')
                else:
                    unicode_parts.append(f'U+{codepoint:05X}')
            
            if not unicode_parts:
                errors.append(f'  無法處理檔案名稱: {filename}')
                continue
            
            new_base = '_'.join(unicode_parts) + suffix

        new_filename = new_base + '.svg'

        old_path = os.path.join(input_dir, filename)
        new_path = os.path.join(output_dir, new_filename)

        try:
            shutil.copy2(old_path, new_path)
            # print(f'  複製: {filename} -> {os.path.basename(output_dir)}/{new_filename}')
            processed += 1
            if processed % 100 == 0:
                print(f"  已處理 {processed} 個檔案...")
        except Exception as e:
            errors.append(f'  複製失敗: {filename} -> {new_filename}: {e}')

    print(f'\n完成！已將 {processed} 個檔案複製並重命名至 "{output_dir}"。')
    if errors:
        print(f'錯誤 ({len(errors)} 個):')
        for err in errors:
            print(err)

if __name__ == '__main__':
    main()
