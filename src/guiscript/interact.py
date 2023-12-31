import pygame
import typing
if typing.TYPE_CHECKING:
    from .manager import Manager

from .state import UIState
from .elements.element import Element
from . import events
from . import common
from . import events


class UIInteract:
    """Update the status of the elements bound to a Manager"""

    def __init__(self, manager: "Manager"):
        # pygame.scrap.init()
        self.manager: "Manager" = manager

        self.hovered_el: Element = None
        self.pressed_el: Element = None
        self.right_pressed_el: Element = None
        self.last_scroll_hovered: Element = None

        self.start_idxs: list[int] = None
        self.last_idxs: list[int] = None
        self.text_select_el: Element = None

    def _logic(self):
        if self.manager._last_rendered is None:
            return

        # text selection
        if self.text_select_el is not None and self.start_idxs is not None:
            lines = common.text_wrap_str(self.text_select_el.text.real_text, self.text_select_el.relative_rect.w, self.text_select_el.style.text.font)
            if UIState.mouse_pressed[0]:
                end_idxs_info = common.text_click_idx(lines, self.text_select_el.style.text.font, UIState.mouse_pos, self.text_select_el.text.text_rect,
                                                      pygame.Vector2(self.text_select_el.absolute_rect.topleft))
                if end_idxs_info is not None:
                    char_i, line_i, tot_i, raw_text = end_idxs_info
                    self.last_idxs = [char_i, line_i, tot_i]
                    if self.text_select_el.text._selection_end_idxs != self.last_idxs:
                        self.text_select_el.text._selection_end_idxs = self.last_idxs
                        self.text_select_el.status.invoke_callback(
                            "on_text_selection_change")

            if self.last_idxs is not None:
                select_rects = common.text_select_rects(self.start_idxs[1], self.start_idxs[0], self.last_idxs[1], self.last_idxs[0],
                                                        lines, self.text_select_el.style.text.font, self.text_select_el.text.text_rect, UIState.mouse_rel.length() != 0)
                if UIState.mouse_pressed[0]:
                    if self.last_idxs[-1] > self.start_idxs[-1]:
                        self.text_select_el.text.set_cursor_index(
                            self.last_idxs[-1]+1)
                    else:
                        self.text_select_el.text.set_cursor_index(
                            self.last_idxs[-1])
                if select_rects:
                    if select_rects != self.text_select_el.text.selection_rects:
                        self.text_select_el.text.selection_rects = select_rects
                        self.text_select_el.set_dirty()
                        self.text_select_el.status.invoke_callback(
                            "on_text_selection_change")

        # we are pressing something
        if self.pressed_el is not None:
            # fire when_pressed
            self.pressed_el.status.invoke_callback("when_pressed")
            events._post_base_event(events.PRESSED, self.pressed_el)
            # update hover
            self.pressed_el.status.hovered = self.pressed_el.absolute_rect.collidepoint(
                UIState.mouse_pos)
            # we are not pressing no more
            if (not UIState.mouse_pressed[0] and not self.pressed_el is self.manager.navigation.tabbed_element) or (self.pressed_el is self.manager.navigation.tabbed_element and not UIState.space_pressed):
                # set pressed
                self.pressed_el.status.pressed = False
                # fire on_stop_press
                self.pressed_el.status.invoke_callbacks(
                    "on_stop_press", "on_click")
                events._post_base_event(events.STOP_PRESS, self.pressed_el)
                events._post_base_event(events.CLICK, self.pressed_el)
                # update selection
                if self.pressed_el.status.can_select:
                    # toggle selection
                    old_selected = self.pressed_el.status.selected
                    self.pressed_el.status.selected = not self.pressed_el.status.selected
                    # fire on_select/on_deselect
                    if old_selected:
                        self.pressed_el.status.invoke_callback("on_deselect")
                        self.pressed_el.buffers.update("selected", False)
                        events._post_base_event(
                            events.DESELECT, self.pressed_el)
                    else:
                        self.pressed_el.status.invoke_callback("on_select")
                        self.pressed_el.buffers.update("selected", True)
                        events._post_base_event(events.SELECT, self.pressed_el)

                # remove pressed el
                self.pressed_el = None
        # we are pressing with right
        elif self.right_pressed_el is not None:
            # fire when_right_pressed
            self.right_pressed_el.status.invoke_callback("when_right_pressed")
            events._post_base_event(
                events.RIGHT_PRESSED, self.right_pressed_el)
            # update hover
            self.right_pressed_el.status.hovered = self.right_pressed_el.absolute_rect.collidepoint(
                UIState.mouse_pos)
            # we aint pressing
            if not UIState.mouse_pressed[1]:
                # set not right pressed and remove right pressed el
                self.right_pressed_el.status.right_pressed = False
                # fire on_stop_right_press
                self.right_pressed_el.status.invoke_callbacks(
                    "on_stop_right_press", "on_right_click")
                events._post_base_event(events.STOP_RIGHT_PRESS,
                                        self.right_pressed_el)
                events._post_base_event(
                    events.RIGHT_CLICK, self.right_pressed_el)
                self.right_pressed_el = None
        else:
            # we aint pressing anything
            last_rendered = self.manager._last_rendered
            # we have something already hovered
            if self.hovered_el is not None:
                # remove hover status, and raycast again
                self.hovered_el.status.hovered = False
                old = self.hovered_el
                self.hovered_el = self.raycast(
                    UIState.mouse_pos, last_rendered.parent if last_rendered else None, True)
                # if we changed hover, fire on_stop_hover
                if old is not self.hovered_el:
                    old.status.invoke_callback("on_stop_hover")
                    events._post_base_event(events.STOP_HOVER, old)
                    if self.last_scroll_hovered is not None:
                        self.last_scroll_hovered.status.scroll_hovered = False
                        self.last_scroll_hovered = None
                else:
                    self.hovered_el.status.hovered = True
            else:
                # we didnt have something hovered so just raycast
                self.hovered_el = self.raycast(
                    UIState.mouse_pos, last_rendered.parent if last_rendered else None, True)
            # we are actually hovering something
            if self.hovered_el is not None:
                # TODO: set scroll hover
                # if was not hovered set hovered and fire on_start_hover
                if not self.hovered_el.status.hovered:
                    self.hovered_el.status.hovered = True
                    self.hovered_el.status.invoke_callback("on_start_hover")
                    self.hovered_el.status.hover_start_time = pygame.time.get_ticks()
                    events._post_base_event(
                        events.START_HOVER, self.hovered_el)
                    self._find_scroll_hovered(self.hovered_el)
                # fire when_hovered
                self.hovered_el.status.invoke_callback("when_hovered")
                events._post_base_event(events.HOVERED, self.hovered_el)
                # we start pressing left
                if UIState.mouse_pressed[0] or (UIState.space_pressed and self.manager.navigation.tabbed_element is self.hovered_el):
                    if not self.hovered_el.status.pressed:
                        # fire on_start_press
                        self.hovered_el.status.pressed = True
                        self.hovered_el.status.invoke_callback(
                            "on_start_press")
                        self.hovered_el.status.press_start_time = pygame.time.get_ticks()
                        events._post_base_event(
                            events.START_PRESS, self.hovered_el)
                        # set pressed and set pressed el
                        self.pressed_el = self.hovered_el
                        self._text_select_start_press(self.pressed_el)
                # we start pressing right
                elif UIState.mouse_pressed[1]:
                    if not self.hovered_el.status.right_pressed:
                        # fire on_start_right_press
                        self.hovered_el.status.right_pressed = True
                        self.hovered_el.status.invoke_callback(
                            "on_start_right_press")
                        self.hovered_el.status.right_press_start_time = pygame.time.get_ticks()
                        events._post_base_event(
                            events.START_RIGHT_PRESS, self.hovered_el)
                        # set right pressed and set right pressed el
                        self.right_pressed_el = self.hovered_el

        if self.manager.cursors.do_override_cursor:
            if self.hovered_el is not None and self.hovered_el.status.active:
                if (rn := self.hovered_el.get_attr("resizer_name")) is not None:
                    if rn in self.manager.cursors.resize_cursors:
                        pygame.mouse.set_cursor(
                            self.manager.cursors.resize_cursors[rn])
                else:
                    pygame.mouse.set_cursor(self.manager.cursors.hover_cursor)
            else:
                pygame.mouse.set_cursor(self.manager.cursors.default_cursor)

    def raycast(self, position: common.Coordinate, start_parent: Element, can_recurse_above=False) -> Element | None:
        """Find the hovered element at a certain position. Extra arguments are used for recursion. Keyboard navigated elements have priority"""
        if self.manager.navigation.tabbed_element is not None:
            return self.manager.navigation.tabbed_element
        if start_parent is None or not start_parent.status.visible:
            return
        if (not start_parent.absolute_rect.collidepoint(position) or start_parent.ignore_raycast) and can_recurse_above:
            return self.raycast(position, start_parent.parent, True)

        for rev_child in reversed(sorted(start_parent.children, key=lambda el: el.z_index)):
            if not rev_child.absolute_rect.collidepoint(position) or not rev_child.status.visible or rev_child.ignore_raycast:
                continue
            if len(rev_child.children) > 0:
                res = self.raycast(position, rev_child)
                if res and res.status.visible:
                    return res
            return rev_child

        if can_recurse_above:
            return self.raycast(position, start_parent.parent, True)

    def _event(self, event: pygame.Event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_c and event.mod & pygame.KMOD_CTRL:
                if self.text_select_el is not None and self.start_idxs is not None and self.last_idxs is not None:
                    lines = common.text_wrap_str(self.text_select_el.text.real_text,
                                                 self.text_select_el.relative_rect.w, self.text_select_el.style.text.font)
                    common.text_select_copy(
                        self.start_idxs[1], self.start_idxs[0], self.last_idxs[1], self.last_idxs[0], lines)

    def _find_scroll_hovered(self, element: Element):
        if element.is_stack() and (element.vscrollbar.status.visible or element.hscrollbar.status.visible):
            element.status.scroll_hovered = True
            self.last_scroll_hovered = element
            return
        if element.parent is not None:
            self._find_scroll_hovered(element.parent)

    def _text_select_start_press(self, element: Element):
        if not element.text.can_select:
            return
        if self.text_select_el is not None:
            self.text_select_el.text.selection_rects = []
            self.text_select_el.set_dirty()
        self.text_select_el = None
        if not (txt := element.text.real_text):
            return
        lines = common.text_wrap_str(
            txt, element.relative_rect.w, element.style.text.font)
        idxs_info = common.text_click_idx(lines, element.style.text.font, UIState.mouse_pos, element.text.text_rect,
                                          pygame.Vector2(element.absolute_rect.topleft))
        if idxs_info is None:
            return
        char_i, line_i, tot_i, raw_text = idxs_info
        self.text_select_el = element
        self.start_idxs = [char_i, line_i, tot_i]
        self.text_select_el.text._selection_start_idxs = self.start_idxs
        self.text_select_el.status.invoke_callback("on_text_selection_change")
