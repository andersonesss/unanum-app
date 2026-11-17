# utils/share_card.py
"""
Общие утилиты для генерации share-карточек.
Используется в app.py: api_generate_card и api_generate_share_card.
"""
from PIL import Image, ImageDraw, ImageFont
import textwrap
import os


def load_font(size):
    """Загружает шрифт, пробуя несколько вариантов, с fallback на дефолтный."""
    paths = [
        os.path.join('static', 'fonts', 'Roboto-Regular.ttf'),
        os.path.join('static', 'fonts', 'Inter-Regular.ttf'),
        "arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        None
    ]
    for p in paths:
        try:
            if p:
                return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


def render_text_layer(text_lines, font, color, shadow_color, shadow_offset, align, width, height, margin, shadow_blur=4):
    """Отрисовывает текст на прозрачном RGBA-слое."""
    text_layer = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    text_draw = ImageDraw.Draw(text_layer)
    y = margin + 100
    for line in text_lines:
        if not line:
            y += 16
            continue
        bbox = text_draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        if align == 'center':
            x = (width - tw) / 2
        elif align == 'right':
            x = width - margin - tw
        else:
            x = margin

        if shadow_blur > 0:
            text_draw.text(
                (x + shadow_offset[0], y + shadow_offset[1]),
                line, fill=shadow_color, font=font
            )
        text_draw.text((x, y), line, fill=color, font=font)
        y += bbox[3] - bbox[1] + 12
    return text_layer


def apply_text_shape(text_img, shape, width, height):
    """Применяет перспективное искажение к текстовому слою."""
    if shape == 'rectangle' or not text_img:
        return text_img
    tw, th = text_img.size
    margin_x = int(tw * 0.15)
    shape_map = {
        'trapezoid_top': (1, 0, margin_x, 0, 0, 1, 0, 0, 0.0003, 0),
        'trapezoid_bottom': (1, 0, -margin_x, 0, 0, 1, 0, 0, -0.0003, 0),
        'pyramid_up': (1, 0, int(tw * 0.3), 0, 0, 1, 0, 0, 0.0005, -0.0005),
        'pyramid_down': (1, 0, -int(tw * 0.3), 0, 0, 1, 0, 0, -0.0005, 0.0005),
    }
    coeffs = shape_map.get(shape)
    if not coeffs:
        return text_img
    return text_img.transform((tw, th), Image.PERSPECTIVE, coeffs)


def wrap_text_to_block(draw, text, font_size, box_w, box_h):
    """Подбирает размер шрифта и переносит текст так, чтобы он полностью заполнил блок.
    Возвращает (список_строк, шрифт, высота_строки, общая_высота).
    """
    test_font = None
    wrapped_lines = []
    line_height = 0
    total_h = 0

    while font_size >= 8:
        test_font = load_font(font_size)
        char_width = draw.textbbox((0, 0), "A", font=test_font)[2]
        chars_per_line = max(1, int(box_w / char_width))
        wrapped_text = textwrap.fill(text if text else '', width=chars_per_line)
        wrapped_lines = wrapped_text.split('\n')
        line_height = draw.textbbox((0, 0), "Ag", font=test_font)[3] + 2
        total_h = len(wrapped_lines) * line_height
        if total_h <= box_h:
            break
        font_size -= 2

    if font_size < 8:
        test_font = load_font(8)
        char_width = draw.textbbox((0, 0), "A", font=test_font)[2]
        chars_per_line = max(1, int(box_w / char_width))
        wrapped_text = textwrap.fill(text if text else '', width=chars_per_line)
        wrapped_lines = wrapped_text.split('\n')
        line_height = draw.textbbox((0, 0), "Ag", font=test_font)[3] + 2
        max_lines = int(box_h // line_height)
        wrapped_lines = wrapped_lines[:max_lines]
        if wrapped_lines:
            wrapped_lines[-1] = wrapped_lines[-1] + '…'
        total_h = len(wrapped_lines) * line_height

    return wrapped_lines, test_font, line_height, total_h


def draw_wrapped_lines(draw, lines, font, color, shadow_color, shadow_offset,
                       min_x, max_x, center_y, box_w, line_height, shadow_blur):
    """Рисует построчно текст внутри заданного bounding box с обрезанием по ширине."""
    y = center_y
    for line in lines:
        lw = draw.textbbox((0, 0), line, font=font)[2]
        while lw > box_w and len(line) > 1:
            line = line[:-1]
            lw = draw.textbbox((0, 0), line + '…', font=font)[2]
            if lw <= box_w:
                line = line + '…'
                lw = draw.textbbox((0, 0), line, font=font)[2]
                break
        lx = min_x
        if lx < min_x:
            lx = min_x
        if lx + lw > max_x:
            lx = max_x - lw
        if shadow_blur > 0:
            draw.text(
                (lx + shadow_offset[0], y + shadow_offset[1]),
                line, fill=shadow_color, font=font
            )
        draw.text((lx, y), line, fill=color, font=font)
        y += line_height