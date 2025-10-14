#!/usr/bin/env python3
"""
Logo Generator Script for Teacher Tools
Скрипт для генерации иконок различных размеров из логотипа
"""

import os
from PIL import Image, ImageDraw
import argparse

def create_icon_from_logo(logo_path, output_size, output_path):
    """Создает иконку заданного размера из логотипа"""
    try:
        # Открываем исходный логотип
        with Image.open(logo_path) as logo:
            # Конвертируем в RGBA если нужно
            if logo.mode != 'RGBA':
                logo = logo.convert('RGBA')
            
            # Изменяем размер с сохранением пропорций
            logo.thumbnail((output_size, output_size), Image.Resampling.LANCZOS)
            
            # Создаем квадратное изображение с прозрачным фоном
            icon = Image.new('RGBA', (output_size, output_size), (0, 0, 0, 0))
            
            # Центрируем логотип
            x = (output_size - logo.width) // 2
            y = (output_size - logo.height) // 2
            icon.paste(logo, (x, y), logo)
            
            # Сохраняем
            icon.save(output_path, 'PNG')
            print(f"[OK] Created icon {output_size}x{output_size}: {output_path}")
            
    except Exception as e:
        print(f"[ERROR] Error creating icon {output_size}x{output_size}: {e}")

def create_default_icon(output_size, output_path):
    """Создает иконку по умолчанию если логотип недоступен"""
    try:
        # Создаем изображение с градиентным фоном
        icon = Image.new('RGBA', (output_size, output_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(icon)
        
        # Создаем градиент (упрощенный)
        for i in range(output_size):
            color_ratio = i / output_size
            r = int(102 + (118 - 102) * color_ratio)  # 667eea -> 764ba2
            g = int(126 + (75 - 126) * color_ratio)
            b = int(234 + (162 - 234) * color_ratio)
            
            draw.line([(i, 0), (i, output_size)], fill=(r, g, b, 255))
        
        # Белый круг
        circle_size = int(output_size * 0.4)
        circle_x = (output_size - circle_size) // 2
        circle_y = (output_size - circle_size) // 2
        
        draw.ellipse([circle_x, circle_y, circle_x + circle_size, circle_y + circle_size], 
                    fill=(255, 255, 255, 230))
        
        # Книга
        book_width = int(output_size * 0.4)
        book_height = int(output_size * 0.3)
        book_x = (output_size - book_width) // 2
        book_y = (output_size - book_height) // 2
        
        draw.rectangle([book_x, book_y, book_x + book_width, book_y + book_height], 
                      fill=(102, 126, 234, 255))
        
        # Линии в книге
        line_width = max(1, output_size // 50)
        for i in range(4):
            line_y = book_y + int(book_height * 0.2) + i * int(book_height * 0.15)
            draw.line([book_x + int(book_width * 0.1), line_y, 
                      book_x + int(book_width * 0.9), line_y], 
                     fill=(255, 255, 255, 255), width=line_width)
        
        icon.save(output_path, 'PNG')
        print(f"[OK] Created default icon {output_size}x{output_size}: {output_path}")
        
    except Exception as e:
        print(f"[ERROR] Error creating default icon: {e}")

def generate_all_icons(logo_path=None, output_dir='static/icons'):
    """Генерирует все необходимые иконки"""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Стандартные размеры для PWA
    pwa_sizes = [16, 32, 57, 60, 72, 76, 96, 114, 120, 128, 144, 152, 180, 192, 384, 512]
    
    # Дополнительные размеры
    additional_sizes = [24, 48, 64, 80, 112, 256, 320, 640]
    
    all_sizes = pwa_sizes + additional_sizes
    
    print(f"[INFO] Generating icons from logo...")
    print(f"[INFO] Output directory: {output_dir}")
    
    if logo_path and os.path.exists(logo_path):
        print(f"[INFO] Using logo: {logo_path}")
        for size in all_sizes:
            output_path = os.path.join(output_dir, f'icon-{size}x{size}.png')
            create_icon_from_logo(logo_path, size, output_path)
    else:
        print("[WARNING] Logo not found, creating default icons")
        for size in all_sizes:
            output_path = os.path.join(output_dir, f'icon-{size}x{size}.png')
            create_default_icon(size, output_path)
    
    print("[SUCCESS] Generation completed!")

def main():
    parser = argparse.ArgumentParser(description='Генератор иконок Teacher Tools')
    parser.add_argument('--logo', '-l', help='Путь к файлу логотипа')
    parser.add_argument('--output', '-o', default='static/icons', help='Папка для сохранения иконок')
    parser.add_argument('--size', '-s', type=int, help='Конкретный размер иконки')
    
    args = parser.parse_args()
    
    if args.size:
        # Генерируем одну иконку
        if args.logo and os.path.exists(args.logo):
            output_path = os.path.join(args.output, f'icon-{args.size}x{args.size}.png')
            create_icon_from_logo(args.logo, args.size, output_path)
        else:
            output_path = os.path.join(args.output, f'icon-{args.size}x{args.size}.png')
            create_default_icon(args.size, output_path)
    else:
        # Генерируем все иконки
        generate_all_icons(args.logo, args.output)

if __name__ == '__main__':
    main()
