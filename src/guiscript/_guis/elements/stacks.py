import pygame
import typing
import inspect

from .element import Element
from ..manager import Manager
from .scrollbars import UIVScrollbar, UIHScrollbar


class UIStack(Element):
    """[Internal] Base element for VStack and HStack"""

    def __init__(self,
                 relative_rect: pygame.Rect,
                 element_id: str = "none",
                 style_id: str = "",
                 parent: Element | None = None,
                 manager: Manager | None = None,
                 scrollbars_style_id: str = "copy",
                 stack_dir_prefix: str = "v"
                 ):
        self._done = False
        super().__init__(relative_rect, element_id, style_id, ("element", "stack", f"{stack_dir_prefix}stack"), parent,
                         manager)
        self.content_x: int = 0
        self.content_y: int = 0
        self.total_x: int = 0
        self.total_y: int = 0
        self.vscrollbar: UIVScrollbar = UIVScrollbar(self, scrollbars_style_id).set_attr("builtin", True)
        self.hscrollbar: UIHScrollbar = UIHScrollbar(self, scrollbars_style_id).set_attr("builtin", True)
        self._done = True
        self.deactivate()
        
    def bind_hscrollbar(self, hscrollbar: UIHScrollbar) -> typing.Self:
        """Register a new horizontal scrollbar and destroy the old one. The scrollbar must be made with guiscript.custom_hscrollbar for it to work properly"""
        self._done = False
        self.hscrollbar.destroy(True)
        self.hscrollbar = hscrollbar
        self._done = True
        return self
    
    def bind_vscrollbar(self, vscrollbar: UIVScrollbar) -> typing.Self:
        """Register a new vertical scrollbar and destroy the old one. The scrollbar must be made with guiscript.custom_vscrollbar for it to work properly"""
        self._done = False
        self.vscrollbar.destroy(True)
        self.vscrollbar = vscrollbar
        self._done = True
        return self

    def is_stack(self) -> bool:
        return True

    def set_scroll(self, pixels_x: int, pixels_y: int) -> typing.Self:
        """Set the scroll offset and update the children position"""
        self.scroll_offset.x = pygame.math.clamp(pixels_x, 0, self.total_x)
        self.scroll_offset.y = pygame.math.clamp(pixels_y, 0, self.total_y)
        for child in self.children:
            child._update_absolute_rect_pos()
        self.vscrollbar._refresh(self.total_y-self.content_y)
        self.hscrollbar._refresh(self.total_x-self.content_x)
        return self

    def scroll_to(self, x: float = 0, y: float = 0) -> typing.Self:
        """Set the scroll offset relative to the content size, where x and y are in range 0-1"""
        self.scroll_offset = pygame.Vector2(self.content_x*x, self.content_y*y)
        for child in self.children:
            child._update_absolute_rect_pos()
        self.vscrollbar._refresh(self.total_y-self.content_y)
        self.hscrollbar._refresh(self.total_x-self.content_x)
        return self
    
    def __enter__(self, *args):
        self._done = False
        return super().__enter__(*args)
    
    def __exit__(self, *args):
        self._done = True
        self._refresh_stack()
        return super().__exit__(*args)


class VStack(UIStack):
    """Organize children vertically using stack style settings"""

    def __init__(self,
                 relative_rect: pygame.Rect,
                 element_id: str = "none",
                 style_id: str = "",
                 parent: Element | None = None,
                 manager: Manager | None = None,
                 scrollbars_style_id: str = "copy"
                 ):
        super().__init__(relative_rect, element_id, style_id, parent,
                         manager, scrollbars_style_id, "v")

    def _refresh_stack(self):
        if not self.manager._running or not self._done:
            return

        style = self.style
        total_x = 0
        total_y = style.stack.padding

        active_children_num = 0
        children_with_fill_y: list[Element] = []
        for i, child in enumerate(self.children):
            if child.ignore_stack or not child.status.visible:
                continue
            if child.relative_rect.w > total_x and not child.style.stack.fill_x:
                total_x = child.relative_rect.w
            if child.style.stack.fill_y:
                active_children_num += 1
                children_with_fill_y.append(child)
                continue
            if i > 0:
                total_y += style.stack.spacing
            total_y += child.relative_rect.h
            active_children_num += 1

        total_y += style.stack.padding
        total_x += style.stack.padding * 2

        old_total_y = total_y
        if len(children_with_fill_y) > 0 and total_y < self.relative_rect.h:
            total_y = self.relative_rect.h

        if (total_x < self.relative_rect.w and style.stack.shrink_x) or \
                (total_x > self.relative_rect.w and style.stack.grow_x):
            self.set_size((total_x, self.relative_rect.h))

        self.content_x = total_x
        self.content_y = total_y

        if style.stack.floating_scrollbars:
            scroll_x = scroll_y = 0
            self.vscrollbar._refresh(0)
            self.hscrollbar._refresh(0)
        else:
            self.vscrollbar._refresh(0)
            scroll_x = 0
            if self.vscrollbar.status.visible:
                scroll_x = style.stack.scrollbar_size
            scroll_y = 0
            self.hscrollbar._refresh(scroll_x)
            if self.hscrollbar.status.visible:
                scroll_y = style.stack.scrollbar_size
                self.vscrollbar._refresh(scroll_y)
                if self.vscrollbar.status.visible:
                    scroll_x = style.stack.scrollbar_size
                    self.hscrollbar._refresh(scroll_x)

        self.total_x = self.content_x+scroll_x
        self.total_y = self.content_y+scroll_y

        if len(children_with_fill_y) > 0:
            space_available = self.relative_rect.h-old_total_y-scroll_y
            space_available -= style.stack.spacing * \
                (len(children_with_fill_y)-1)
            if space_available < 0:
                space_available = 0
            space_for_each_child = space_available/len(children_with_fill_y)
            for child in children_with_fill_y:
                child.set_size((child.relative_rect.w, space_for_each_child))

        spacing = style.stack.spacing
        if style.stack.anchor == "max_spacing":
            if total_y < self.relative_rect.h-scroll_y:
                remaining = self.relative_rect.h-scroll_y-total_y
                total_y = self.relative_rect.h-scroll_y
                spacing = remaining/(max(active_children_num-1, 1)) + \
                    style.stack.padding/(max(active_children_num-1, 1))

        current_y = 0
        if total_y < (self.relative_rect.h-scroll_y):
            if style.stack.shrink_y:
                self.set_size((self.relative_rect.w, total_y), True, refresh_stack=False)
            else:
                match style.stack.anchor:
                    case "center":
                        current_y = (self.relative_rect.h -
                                     scroll_y)//2-total_y//2
                    case "bottom" | "right":
                        current_y = (self.relative_rect.h-scroll_y)-total_y
        elif total_y > self.relative_rect.h and style.stack.grow_y:
            self.set_size((self.relative_rect.w, total_y), True, refresh_stack=False)
        current_y += style.stack.padding

        i_o = 0
        for i, child in enumerate(self.children):
            if child.ignore_stack or not child.status.visible:
                i_o += 1
                continue
            if i > i_o:
                current_y += spacing
            child_x = style.stack.padding
            if not child.style.stack.fill_x:
                if child.relative_rect.w < (self.relative_rect.w-scroll_x):
                    match child.style.stack.align:
                        case "center":
                            child_x = (self.relative_rect.w-scroll_x)//2 - \
                                child.relative_rect.w//2
                        case "right" | "bottom":
                            child_x = (self.relative_rect.w-scroll_x) - \
                                child.relative_rect.w-style.stack.padding
            else:
                child.set_size(
                    (self.relative_rect.w-style.stack.padding*2-scroll_x, child.relative_rect.h))
            child.set_relative_pos((child_x, current_y))
            current_y += child.relative_rect.h


class Box(VStack):
    """A vertical container (direction doesn't really matter) that is supposed to contain only 1 user child (not enforced) with shortcuts to access and change it"""
    def __init__(self,
                 relative_rect: pygame.Rect,
                 child: Element | None = None,
                 element_id: str = "none",
                 style_id: str = "",
                 parent: Element | None = None,
                 manager: Manager | None = None,
                 scrollbars_style_id: str = "copy"
                 ):
        super().__init__(relative_rect, element_id, style_id, parent,
                         manager, scrollbars_style_id)
        self.child: Element|None = None
        self.set_child(child)
        
    def set_child(self, element: Element|None) -> typing.Self:
        """Set the box's child or remove it by passing None"""
        if self.child is not None:
            self.child.set_parent(None)
        if element is not None:
            element.set_parent(self)
        self.child = element
        return self
    

class HStack(UIStack):
    """Organize children horizontally using stack style settings"""

    def __init__(self,
                 relative_rect: pygame.Rect,
                 element_id: str = "none",
                 style_id: str = "",
                 parent: Element | None = None,
                 manager: Manager | None = None,
                 scrollbars_style_id: str = "copy"
                 ):
        super().__init__(relative_rect, element_id, style_id, parent,
                         manager, scrollbars_style_id, "h")

    def _refresh_stack(self):
        if not self.manager._running or not self._done:
            return
        style = self.style
        total_x = style.stack.padding
        total_y = 0

        active_children_num = 0
        children_with_fill_x: list[Element] = []
        for i, child in enumerate(self.children):
            if child.ignore_stack or not child.status.visible:
                continue

            if child.relative_rect.h > total_y and not child.style.stack.fill_y:
                total_y = child.relative_rect.h
            if child.style.stack.fill_x:
                active_children_num += 1
                children_with_fill_x.append(child)
                continue
            if i > 0:
                total_x += style.stack.spacing
            total_x += child.relative_rect.w
            active_children_num += 1

        total_x += style.stack.padding
        total_y += style.stack.padding * 2

        old_total_x = total_x
        if len(children_with_fill_x) > 0 and total_x < self.relative_rect.w:
            total_x = self.relative_rect.w

        if (total_y < self.relative_rect.h and style.stack.shrink_y) or \
                (total_y > self.relative_rect.h and style.stack.grow_y):
            self.set_size((self.relative_rect.w, total_y))

        self.content_x = total_x
        self.content_y = total_y

        if style.stack.floating_scrollbars:
            scroll_x = scroll_y = 0
            self.vscrollbar._refresh(0)
            self.hscrollbar._refresh(0)
        else:
            self.vscrollbar._refresh(0)
            scroll_x = 0
            if self.vscrollbar.status.visible:
                scroll_x = style.stack.scrollbar_size
            scroll_y = 0
            self.hscrollbar._refresh(scroll_x)
            if self.hscrollbar.status.visible:
                scroll_y = style.stack.scrollbar_size
                self.vscrollbar._refresh(scroll_y)
                if self.vscrollbar.status.visible:
                    scroll_x = style.stack.scrollbar_size
                    self.hscrollbar._refresh(scroll_x)

        self.total_x = self.content_x+scroll_x
        self.total_y = self.content_y+scroll_y

        if len(children_with_fill_x) > 0:
            space_available = self.relative_rect.w-old_total_x-scroll_x
            space_available -= style.stack.spacing * \
                (len(children_with_fill_x)-1)
            space_for_each_child = space_available/len(children_with_fill_x)
            for child in children_with_fill_x:
                child.set_size((space_for_each_child, child.relative_rect.h))

        spacing = style.stack.spacing
        if style.stack.anchor == "max_spacing":
            if total_x < self.relative_rect.w-scroll_x:
                remaining = self.relative_rect.w-scroll_x-total_x
                total_x = self.relative_rect.w-scroll_x
                spacing = remaining/(max(active_children_num-1, 1)) + \
                    style.stack.padding/(max(active_children_num-1, 1))

        current_x = style.stack.padding
        if total_x < (self.relative_rect.w-scroll_x):
            if style.stack.shrink_x:
                self.set_size((total_x, self.relative_rect.h))
            else:
                match style.stack.anchor:
                    case "center":
                        current_x = (self.relative_rect.w -
                                     scroll_x)//2-total_x//2
                    case "right" | "bottom":
                        current_x = (self.relative_rect.w-scroll_x)-total_x
        elif total_x > self.relative_rect.w and style.stack.grow_x:
            self.set_size((total_x, self.relative_rect.h))

        i_o = 0
        for i, child in enumerate(self.children):
            if child.ignore_stack or not child.status.visible:
                i_o += 1
                continue
            if i > i_o:
                current_x += spacing
            child_y = style.stack.padding
            if not child.style.stack.fill_y:
                if child.relative_rect.h < (self.relative_rect.h-scroll_y):
                    match child.style.stack.align:
                        case "center":
                            child_y = (self.relative_rect.h-scroll_y)//2 - \
                                child.relative_rect.h//2
                        case "bottom" | "right":
                            child_y = (self.relative_rect.h-scroll_y) - \
                                child.relative_rect.h-style.stack.padding
            else:
                child.set_size(
                    (child.relative_rect.w, self.relative_rect.h-style.stack.padding*2))
            child.set_relative_pos((current_x, child_y))
            current_x += child.relative_rect.w
