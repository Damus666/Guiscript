import math
import pygame
import typing
import warnings
if typing.TYPE_CHECKING:
    from .elements.element import Element

from .error import UIError
from .state import UIState


Coordinate: typing.TypeAlias = typing.Iterable[float] | pygame.Vector2
Color: typing.TypeAlias = typing.Iterable[int] | str | pygame.Color
StatusCallback: typing.TypeAlias = typing.Callable[[
    "Element"], typing.Any] | None
CursorLike: typing.TypeAlias = pygame.Cursor | int


class UIAnchorData:
    def __init__(self, target: "Element", self_anchor: str, target_anchor: str, offset: Coordinate):
        self.target: "Element" = target
        self.self_anchor: str = self_anchor
        self.target_anchor: str = target_anchor
        self.offset: float = offset
        

def warn(message: str):
    warnings.warn(message, UserWarning)


def style_id_or_copy(element: "Element", style_id: str) -> str:
    return element.style_id if style_id == "copy" else style_id


def align_text(t_rect: pygame.Rect, el_rect: pygame.Rect, padding: int, y_padding: int, align: str) -> pygame.Rect:
    match align:
        case "center":
            t_rect.center = el_rect.center
        case "topleft":
            t_rect.topleft = (el_rect.left+padding, el_rect.top+y_padding)
        case "topright":
            t_rect.topright = (el_rect.right-padding, el_rect.top+y_padding)
        case "bottomleft":
            t_rect.bottomleft = (el_rect.left+padding,
                                 el_rect.bottom-y_padding)
        case "bottomright":
            t_rect.bottomright = (el_rect.right-padding,
                                  el_rect.bottom-y_padding)
        case "midleft" | "left":
            t_rect.midleft = (el_rect.left+padding, el_rect.centery)
        case "midright" | "right":
            t_rect.midright = (el_rect.right-padding, el_rect.centery)
        case "midtop" | "top":
            t_rect.midtop = (el_rect.centerx, el_rect.top+y_padding)
        case "midbottom" | "bottom":
            t_rect.midbottom = (el_rect.centerx, el_rect.bottom-y_padding)
        case _:
            raise UIError(f"Unsupported text align: '{align}'")
    return t_rect


def text_wrap_str(text: str, wrapsize: int, font: pygame.Font) -> list[str]:
    text = text.strip()
    if not text:
        return []
    paragraphs = text.split("\n")
    paragraph_lines = []
    space = font.size(' ')[0]
    for paragraph in paragraphs:
        words = paragraph.split(' ')
        x, y, maxw, i = 0, 0, wrapsize, 0
        lines = []
        line = ""
        for abs_i, word in enumerate(words):
            if not word:
                continue
            wordw, wordh = font.render(word, True, (0, 0, 0)).get_size()
            if i != 0:
                line += " "
            line += word
            if x + wordw >= maxw:
                x = i = 0
                y += wordh
                if abs_i != 0:
                    line = line.removesuffix(" "+word)
                lines.append(line)
                if abs_i != 0:
                    line = word
            x += wordw
            if x != 0:
                x += space
            i += 1
        lines.append(line)
        paragraph_lines += lines
    return paragraph_lines


def line_size_x(font: pygame.Font, line: str) -> int:
    size = 0
    for c in line:
        size += font.size(c)[0]
    return size


def text_click_idx(lines: list[str], font: pygame.Font, pos: pygame.Vector2, rect: pygame.Rect, absolute_topleft: pygame.Vector2) -> tuple[int, int, int, str] | None:
    if len(lines) <= 0:
        return
    rel_pos = pos-absolute_topleft
    if not rect.collidepoint(rel_pos):
        return
    line_idx = int((rel_pos.y-rect.top)//font.get_height())
    if line_idx < 0 or line_idx >= len(lines):
        return
    line = lines[line_idx]
    if not line:
        return
    tot_w = char_i = 0
    start_x = rect.left
    if font.align == pygame.FONT_CENTER:
        start_x = rect.left+rect.w//2-line_size_x(font, line)//2
    elif font.align == pygame.FONT_RIGHT:
        start_x = rect.left+rect.w-line_size_x(font, line)
    if rel_pos.x <= start_x:
        return
    for i, char in enumerate(line):
        char_w = font.size(char)[0]
        tot_w += char_w
        if tot_w+start_x >= rel_pos.x:
            char_i = i
            break
    else:
        return
    tot_i = 0
    if line_idx > 0:
        for l in lines[:line_idx]:
            tot_i += len(l)
    tot_i += char_i
    return char_i, line_idx, tot_i, "".join(lines)


def text_select_rects(start_li: int, start_ci: int, end_li: int, end_ci: int, lines: list[str], font: pygame.Font, rect: pygame.Rect, rel_move: bool = False) -> list[pygame.Rect]:
    if start_li > end_li:
        start_li, end_li = end_li, start_li
        start_ci, end_ci = end_ci, start_ci
    rects = []
    font_h = font.get_height()
    try:
        if start_li == end_li:
            line = lines[start_li]
            offset = 0
            if font.align == pygame.FONT_CENTER:
                offset = rect.w//2-line_size_x(font, line)//2
            elif font.align == pygame.FONT_RIGHT:
                offset = rect.w-line_size_x(font, line)
            if start_ci == end_ci:
                if not rel_move or not UIState.mouse_pressed[0]:
                    return rects
                char = lines[start_li][start_ci]
                rects.append(pygame.Rect(rect.left+offset+line_size_x(font, line[:start_ci]), font_h*start_li+rect.top, line_size_x(font, char), font_h))
                return rects
            if start_ci > end_ci:
                start_ci, end_ci = end_ci, start_ci
            rects.append(pygame.Rect(rect.left+offset+line_size_x(font, line[:start_ci]),
                                     font_h*start_li+rect.top, line_size_x(font, line[start_ci:end_ci+1]), font_h))
        else:
            mid_lines = lines[start_li+1:end_li]
            start_line = lines[start_li]
            end_line = lines[end_li]
            start_offset = end_offset = 0
            if font.align == pygame.FONT_CENTER:
                start_offset = rect.w//2-line_size_x(font, start_line)//2
                end_offset = rect.w//2-line_size_x(font, end_line)//2
            elif font.align == pygame.FONT_RIGHT:
                start_offset = rect.w-line_size_x(font, start_line)
                end_offset = rect.w-line_size_x(font, end_line)
            rects.append(pygame.Rect(rect.left+start_offset+line_size_x(font, start_line[:start_ci]),
                                     font_h*start_li+rect.top, line_size_x(font, start_line[start_ci:]), font_h))
            rects.append(pygame.Rect(rect.left+end_offset, font_h*end_li +
                         rect.top, line_size_x(font, end_line[:end_ci+1]), font_h))
            for i, line in enumerate(mid_lines):
                offset = 0
                if font.align == pygame.FONT_CENTER:
                    offset = rect.w//2-line_size_x(font, line)//2
                elif font.align == pygame.FONT_RIGHT:
                    offset = rect.w-line_size_x(font, line)
                rects.append(pygame.Rect(rect.left+offset, font_h *
                             (i+start_li+1)+rect.top, line_size_x(font, line), font_h))
    except Exception as e:
        return rects
    return rects


def text_select_copy(start_li: int, start_ci: int, end_li: int, end_ci: int, lines: list[str]):
    copy_str = ""
    if start_li > end_li:
        start_li, end_li = end_li, start_li
        start_ci, end_ci = end_ci, start_ci
    if start_li == end_li:
        if start_ci > end_ci:
            start_ci, end_ci = end_ci, start_ci
        copy_str = lines[start_li][start_ci:end_ci+1]
    else:
        mid_lines = lines[start_li+1:end_li]
        copy_str += " "*start_ci+lines[start_li][start_ci:]+"\n"
        for line in mid_lines:
            copy_str += line+"\n"
        copy_str += lines[end_li][:end_ci]
    pygame.scrap.put_text(copy_str)


def generate_menu_surface(original_image: pygame.Surface, width: int, height: int, border: int) -> pygame.Surface:
    if border < 1:
        return original_image
    # setup
    s, s2 = border, border*2
    width, height = int(width), int(height)
    menu_surf: pygame.Surface = original_image
    mw, mh = menu_surf.get_width(), menu_surf.get_height()
    # main surfs
    try:
        big_surf = pygame.Surface((width, height), pygame.SRCALPHA)
    except pygame.error:
        return original_image
    big_surf.fill(0)
    inner_surf = pygame.transform.scale(menu_surf.subsurface(
        (s, s, mw-s2, mh-s2)), (max(width-s2, 1), max(height-s2, 1)))
    # corners
    topleft = menu_surf.subsurface((0, 0, s, s))
    topright = menu_surf.subsurface((mw-s, 0, s, s))
    bottomleft = menu_surf.subsurface((0, mh-s, s, s))
    bottomright = menu_surf.subsurface((mw-s, mh-s, s, s))
    # sides
    top = pygame.transform.scale(menu_surf.subsurface(
        (s, 0, mw-s2, s)), (max(width-s2, 1), s))
    bottom = pygame.transform.scale(menu_surf.subsurface(
        (s, mh-s, mw-s2, s)), (max(width-s2, 1), s))
    left = pygame.transform.scale(menu_surf.subsurface(
        (0, s, s, mh-s2)), (s, max(height-s2, 1)))
    right = pygame.transform.scale(menu_surf.subsurface(
        (mw-s, s, s, mh-s2)), (s, max(height-s2, 1)))
    # blitting
    big_surf.blit(inner_surf, (s, s))
    big_surf.blit(topleft, (0, 0))
    big_surf.blit(topright, (width-s, 0))
    big_surf.blit(bottomleft, (0, height-s))
    big_surf.blit(bottomright, (width-s, height-s))
    big_surf.blit(top, (s, 0))
    big_surf.blit(bottom, (s, height-s))
    big_surf.blit(left, (0, s))
    big_surf.blit(right, (width-s, s))
    # return
    return big_surf


def linear(t: float) -> float:
    return t


def ease_in(t: float) -> float:
    return t * t


def ease_out(t: float) -> float:
    return t * (2 - t)


def ease_in_quad(t: float) -> float:
    return t * t


def ease_out_quad(t: float) -> float:
    return t * (2 - t)


def ease_in_cubic(t: float) -> float:
    return t * t * t


def ease_out_cubic(t: float) -> float:
    return 1 - (1 - t) ** 3


def ease_in_quart(t: float) -> float:
    return t * t * t * t


def ease_out_quart(t: float) -> float:
    return 1 - (1 - t) ** 4


def ease_in_quint(t: float) -> float:
    return t * t * t * t * t


def ease_out_quint(t: float) -> float:
    return 1 - (1 - t) ** 5


def ease_in_sine(t: float) -> float:
    return 1 - math.cos((t * math.pi) / 2)


def ease_out_sine(t: float) -> float:
    return math.sin((t * math.pi) / 2)


def ease_in_expo(t: float) -> float:
    return 0 if t == 0 else 2 ** (10 * (t - 1))


def ease_out_expo(t: float) -> float:
    return 1 if t == 1 else 1 - 2 ** (-10 * t)


def ease_out_circ(t: float) -> float:
    return math.sqrt(abs(1 - (t - 1) * (t - 1)))


def hex_to_rgba(hex: str, a: bool = True) -> tuple[int]:
    hex = hex.replace("#", "").strip()
    return tuple(int(hex[i:i+2], 16) for i in (0, 2, 4)) if not a else tuple(int(hex[i:i+2], 16) for i in (0, 2, 4, 6))
    
    
def rgba_to_hex(r,g,b,a) -> str:
    return '#{:02x}{:02x}{:02x}'.format(r, g, b) if a is None else '#{:02x}{:02x}{:02x}{:02x}'.format(r, g, b, a)


ANIMATION_FUNCTIONS = {
    'linear': linear,
    'ease_in': ease_in,
    'ease_out': ease_out,
    'ease_in_quad': ease_in_quad,
    'ease_out_quad': ease_out_quad,
    'ease_in_cubic': ease_in_cubic,
    'ease_out_cubic': ease_out_cubic,
    'ease_in_quart': ease_in_quart,
    'ease_out_quart': ease_out_quart,
    'ease_in_quint': ease_in_quint,
    'ease_out_quint': ease_out_quint,
    'ease_in_sine': ease_in_sine,
    'ease_out_sine': ease_out_sine,
    'ease_in_expo': ease_in_expo,
    'ease_out_expo': ease_out_expo,
    'ease_out_circ': ease_out_circ,
}


DEFAULT_CALLBACKS: list[str] = [
    "when_hovered",
    "when_pressed",
    "when_right_pressed",
    "on_start_hover",
    "on_start_press",
    "on_start_right_press",
    "on_stop_hover",
    "on_stop_press",
    "on_stop_right_press",
    "on_select",
    "on_deselect",
    "on_click",
    "on_right_click",
    "on_move",
    "on_first_frame",
    "on_animation_end",
    "on_position_change",
    "on_size_change",
    "on_style_change",
    "on_build",
    "on_resize",
    "on_drag",
    "on_text_selection_change"
]


Z_INDEXES = {
    "ghost": -99,
    "element": 0,
    "scrollbar": 999,
    "menu": 1999,
    "window-start": 2000,
    "window-end": 9998,
    "resizer": 9999,
    "tooltip": 10000,
}


STYLE_ANIMATION_TYPES = {
    "stack": {
        "spacing": "number",
        "padding": "number",
        "scrollbar_size": "number"
    },
    "bg": {
        "color": "color",
        "border_radius": "number"
    },
    "image": {
        "padding": "number",
        "border_radius": "number",
        "border_size": "number",
        "border_scale": "number",
        "outline_width": "number",
        "outline_color": "color"
    },
    "shape": {
        "color": "color",
        "outline_width": "number",
        "padding": "number",
        "rect_border_radius": "number",
        "ellipse_padding_x": "number",
        "ellipse_padding_y": "number"
    },
    "text": {
        "color": "color",
        "selection_color": "color",
        "padding": "number",
        "y_padding": "number",
        "font_size": "number"
    },
    "icon": {
        "scale": "number",
        "padding": "number"
    },
    "outline": {
        "color": "color",
        "navigation_color": "color",
        "width": "number",
        "border_radius": "number"
    }
}

DEFAULT_STYLE_GSS: str = """
/ BUILTIN ELEMENT TYPES
text:: {
    text.enabled true;
    bg.enabled false;
    outline.enabled false;
}

icon:: {
    icon.enabled true;
    outline.enabled false;
    bg.enabled false;
}

button:: {
    text.enabled true;
    outline.enabled true;
    bg.enabled true;
}

imagebutton, iconbutton:: {
    text.enabled false;
}

image:: {
    image.enabled true;
    image.outline_width 1;
}

stack, scrollbar, slideshow, slider_bar, player, window::{
    bg.color $DARK_COLOR;
}

checkbox:hover: {
    shape.enabled false;
    text.enabled false;
}

checkbox:press {
    shape.enabled true;
    text.enabled false;
}

slideshow, gif, videoplayer_video, videoplayer_control_stack, dropmenu, modal_container:: {
    bg.enabled false;
    outline.enabled false;
}

slider:: {
    bg.enabled false;
    outline.enabled false;
}

videoplayer:: {
    image.enabled true;
}

progressbar:: {
    shape.enabled true;
    shape.type rect;
}

dropmenu:: {
    stack.padding 0;
}

selectionlist:: {
    stack.padding 2;
    stack.spacing 2;
    stack.anchor top;
}

line:: {
    bg.color (50, 50, 50);
    bg.border_radius 1;
    outline.border_radius 1;
}

entry:: {
    stack.scroll_y false;
    stack.floating_scrollbars true;
}

textbox:: {
    stack.floating_scrollbars true;
    stack.anchor top;
}

window:: {
    stack.padding 3;
}

modal_container:: {
    image.fill true;
    image.enabled true;
    image.fill_color black;
    image.padding 0;
    image.border_radius 0;
    image.alpha 180;
    image.image 'builtin.1x1';
}

soundplayer:: {
    stack.scroll_x false;
    stack.scroll_y false;
}

/ INNER ELEMENTS
colorpicker_preview_image:: {
    stack.fill_x true;
    stack.fill_y true;
}

colorpicker_row:: {
    stack.fill_x true;
}

colorpicker_slider:: {
    stack.fill_x true;
}

colorpicker_hex_entry:: {
    stack.fill_x true;
}

colorpicker_preview:: {
    image.image 'builtin.1x1';
    bg.enabled false;
    outline.enabled false;
    image.fill true;
}

filedialog_button:: {
    stack.fill_y true;
}

filedialog_back_button, filedialog_home_button:: {
    text.font_name googleicons;
    text.font_size 22;
}

filedialog_path_entry:: {
    stack.fill_y true;
    stack.fill_x true;
}

filedialog_selectionlist:: {
    stack.fill_y true;
    stack.fill_x true;
}

filedialog_row:: {
    stack.fill_x true;
}

filedialog_bottom_row:: {
    stack.anchor right;
}

filedialog_content:: {
    stack.scroll_x false;
    stack.scroll_y false;
}

entry_text:: {
    text.do_wrap false;
    text.grow_x true;
    stack.fill_y true;
    stack.align left;
    text.cursor_enabled true;
}

textbox_text:: {
    text.do_wrap false;
    text.grow_x true;
    text.grow_y true;
    stack.align left;
    text.cursor_enabled true;
    text.align topleft;
    text.font_align left;
}

slideshow_arrow:: {
    text.font_name googleicons;
    text.font_size 22;
    bg.enabled false;
    outline.enabled false;
}

soundplayer_button, videoplayer_button:: {
    text.font_name googleicons;
    text.font_size 22;
    bg.enabled false;
    outline.enabled false;
}

videoplayer_control_stack:: {
    stack.scroll_x false;
    stack.scroll_y false;
}

dropmenu_arrow::{
    text.font_name googleicons;
    text.font_size 22;
}

dropmenu_option, selectionlist_option:: {
    stack.fill_x true;
    outline.enabled false;
    bg.border_radius 0;
    outline.border_radius 0;
}

dropmenu_menu:: {
    stack.grow_y true;
    stack.padding 2;
    stack.spacing 2;
}

slideshow_arrow, soundplayer_button, videoplayer_button:hover:press {
    bg.enabled true;
}

tooltip_title:: {
    text.font_size 23;
}

tooltip_description:: {
    text.font_size 20;
}

resizer:press: {
    bg.enabled false;
    outline.enabled false;
    text.enabled false;
    image.enabled false;
    icon.enabled false;
    shape.enabled false;
}

resizer:hover {
    bg.enabled true;
}

window_title:: {
    stack.fill_x true;
    stack.fill_y true;
    text.align left;
    text.font_align left;
    text.do_wrap false;
}

window_collapse_button:: {
    text.font_name googleicons;
}

/ BUILTIN STYLE GROUPS
.inactive:: {
    bg.color $DARK_COLOR;
}

.entry_disabled_text:: {
    text.color (180, 180, 180);
}

.fildialog_selectionlist_option:: {
    text.align left;
    text.font_align left;
}

.active_cont:hover {
    bg.color (32, 32, 32);
}

.active_cont:press {
    bg.color (17, 17, 17);
}

.active_cont {
    bg.color (25, 25, 25);
}

.invis_cont, invisible_container:: {
    bg.enabled false;
    outline.enabled false;
    stack.padding 0;
    stack.floating_scrollbars true;
}

.invisible:: {
    bg.enabled false;
    outline.enabled false;
    text.enabled false;
    image.enabled false;
    icon.enabled false;
    shape.enabled false;
    stack.padding 0;
    stack.floating_scrollbars true;
}

.icons_font:: {
    text.font_name googleicons;
}

.no_scroll:: {
    stack.scroll_x false;
    stack.scroll_y false;
}

.no_padding:: {
    stack.padding 0;
    text.padding 0;
    image.padding 0;
    shape.padding 0;
}

.fill:: {
    stack.fill_x true;
    stack.fill_y true;
}

.fill_x:: {
    stack.fill_x true;
}

.fill_y:: {
    stack.fill_y true;
}

.resize_x:: {
    stack.grow_x true;
    stack.shrink_x true;
}

.resize_y:: {
    stack.grow_y true;
    stack.shrink_y true;
}

.resize:: {
    stack.grow_x true;
    stack.shrink_x true;
    stack.grow_y true;
    stack.shrink_y true;
}
"""
