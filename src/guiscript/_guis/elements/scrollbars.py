import pygame

from .element import Element
from ..state import UIState
from .. import common


class UIScrollbar(Element):
    """[Internal] Base class for UIVScrollbar and UIHScrollbar"""

    def __init__(self, stack: Element, style_id: str, scrollbar_dir_prefix: str):
        super().__init__(pygame.Rect(0, 0, 10, 10), stack.element_id+f"_{scrollbar_dir_prefix}scrollbar", common.style_id_or_copy(stack, style_id),
                         ("element", "scrollbar", f"{scrollbar_dir_prefix}scrollbar"), stack, stack.manager)
        self.set_ignore(True, True).set_can_destroy(
            False).deactivate().set_z_index(common.Z_INDEXES["scrollbar"])
        self.handle: Element = Element(pygame.Rect(
            0, 0, 10, 10), self.element_id+"_handle", self.style_id, ("element", "handle", "scrollbar_handle", f"{scrollbar_dir_prefix}scrollbar_handle"), self, self.manager)
        self._is_custom: bool = False
        
    def _refresh(self):
        ...


class UIVScrollbar(UIScrollbar):
    """[Internal] Element used for scrolling vertically in a stack"""

    def __init__(self, stack: Element, style_id: str):
        super().__init__(stack, style_id, "v")

    def _refresh(self, scroll_y):
        style = self.parent.style.stack

        if not self._is_custom:
            self.set_relative_pos(
                (self.parent.relative_rect.w-style.scrollbar_size, 0))
            self.set_size(
                (style.scrollbar_size, self.parent.relative_rect.h), False)

        if not style.scroll_y or style.grow_y:
            self.status.visible = False
            return
        if self.parent.total_y <= self.parent.relative_rect.h:
            if self.parent.scroll_offset.y != 0:
                self.parent.scroll_offset.y = 0
                self.handle.set_relative_pos((0, 0))
                for child in self.parent.children:
                    child._update_absolute_rect_pos()
            self.status.visible = False
            return

        self.status.visible = True

        handle_y = (self.relative_rect.h*(self.relative_rect.h -
                    scroll_y))/(self.parent.content_y+0.000001)
        self.handle.set_size((style.scrollbar_size, max(min(
            handle_y, self.relative_rect.h), self.manager.min_scroll_handle_size)), False)
        if self.parent.total_y != 0:
            self.handle.set_relative_pos((0, (self.relative_rect.h/self.parent.total_y)*self.parent.scroll_offset.y))

    def on_logic(self):
        if not self.status.visible or not self.parent.status.scroll_hovered:
            return

        prev_y = self.handle.relative_rect.y

        if self.handle.status.pressed and self.handle.status.active:
            self.handle.set_relative_pos(
                (0, self.handle.relative_rect.y+UIState.mouse_rel[1]))

        if UIState.mouse_wheel.y and not UIState.keys_pressed[pygame.K_LCTRL]:
            self.handle.set_relative_pos(
                (0, self.handle.relative_rect.y-(UIState.mouse_wheel.y*self.manager.scroll_multiplier)))

        if self.handle.relative_rect.y < 0:
            self.handle.set_relative_pos((0, 0))
        elif self.handle.relative_rect.bottom > self.relative_rect.h:
            self.handle.set_relative_pos(
                (0, self.relative_rect.h-self.handle.relative_rect.h))

        if self.handle.relative_rect.y != prev_y:
            self.parent.scroll_offset.y = (
                self.handle.relative_rect.y*(self.parent.content_y-self.parent.style.stack.scrollbar_size))/self.relative_rect.h
            for child in self.parent.children:
                child._update_absolute_rect_pos()
            self.status.invoke_callback("on_move")


class UIHScrollbar(UIScrollbar):
    """Element used for scrolling horizontally in a stack"""

    def __init__(self, stack: Element, style_id: str):
        super().__init__(stack, style_id, "h")

    def _refresh(self, scroll_x):
        style = self.parent.style.stack

        if not self._is_custom:
            x_remove = style.scrollbar_size if self.parent.vscrollbar.status.visible else 0
            self.set_relative_pos(
                (0, self.parent.relative_rect.h-style.scrollbar_size))
            self.set_size((self.parent.relative_rect.w -
                        x_remove, style.scrollbar_size), False)

        if not style.scroll_x or style.grow_x:
            self.status.visible = False
            return
        if self.parent.total_x <= self.parent.relative_rect.w:
            if self.parent.scroll_offset.x != 0:
                self.parent.scroll_offset.x = 0
                self.handle.set_relative_pos((0, 0))
                for child in self.parent.children:
                    child._update_absolute_rect_pos()
            self.status.visible = False
            return
        self.status.visible = True

        handle_x = (self.relative_rect.w*(self.relative_rect.w -
                    scroll_x))/(self.parent.content_x+0.000001)
        self.handle.set_size(
            (max(min(handle_x, self.relative_rect.w), self.manager.min_scroll_handle_size), style.scrollbar_size), False)
        if self.parent.total_x != 0:
            self.handle.set_relative_pos(((self.relative_rect.w/self.parent.total_x)*self.parent.scroll_offset.x, 0))

    def on_logic(self):
        if not self.status.visible or not self.parent.status.scroll_hovered:
            return

        prev_x = self.handle.relative_rect.x

        if self.handle.status.pressed and self.handle.status.active:
            self.handle.set_relative_pos(
                (self.handle.relative_rect.x+UIState.mouse_rel[0], 0))

        if UIState.mouse_wheel.y and (UIState.keys_pressed[pygame.K_LCTRL] or not self.parent.vscrollbar.status.visible):
            self.handle.set_relative_pos(
                (self.handle.relative_rect.x-UIState.mouse_wheel.y*self.manager.scroll_multiplier, 0))
        elif UIState.mouse_wheel.x:
            self.handle.set_relative_pos(
                (self.handle.relative_rect.x-UIState.mouse_wheel.x*self.manager.scroll_multiplier, 0))

        if self.handle.relative_rect.x < 0:
            self.handle.set_relative_pos((0, 0))
        elif self.handle.relative_rect.right > self.relative_rect.w:
            self.handle.set_relative_pos(
                (self.relative_rect.w-self.handle.relative_rect.w, 0))

        if self.handle.relative_rect.x != prev_x:
            x_add = self.parent.style.stack.scrollbar_size if self.parent.vscrollbar.status.visible and not self.parent.style.stack.floating_scrollbars else 0
            handle_size = ((self.relative_rect.w+x_add) *
                           self.handle.relative_rect.w)/max(1, self.relative_rect.w)
            handle_x = ((self.relative_rect.w-handle_size)*self.handle.relative_rect.x) / \
                max(self.relative_rect.w-self.handle.relative_rect.w, 0.0001)
            self.parent.scroll_offset.x = (
                handle_x*(self.parent.content_x-x_add/2))/self.relative_rect.w
            for child in self.parent.children:
                child._update_absolute_rect_pos()
            self.status.invoke_callback("on_move")
