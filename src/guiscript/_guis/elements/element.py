import pygame
import typing
if typing.TYPE_CHECKING:
    from ..manager import Manager
    from .root import UIRoot

from ..state import UIState
from ..error import UIError
from ..status import UIStatus
from ..sound import UISounds
from ..buffer import UIBuffers
from ..tooltip import Tooltips
from ..animation import UIPropertyAnim
from ..style import UIStyleGroup, UIStyles, UIStyle
from ..enums import AnimRepeatMode, AnimEaseFunc, AnimPropertyType
from .. import components as comps
from .. import common
from .. import enums
from .. import events


class Element:
    """
    Base class for elements\n
    Use the generator syntax 'with element:...' to set it as the current parent

    relative_rect -> set the starting position and size\n
    element_id -> custom element identifier for styles and events\n
    style_id -> custom style group id to set the style\n
    element_types -> tuple of types the element is used for styles\n
    parent -> the element parent or optionally None if you are in a context manager\n
    manager -> the manager the element is bound to or optionally None if there is a current manager\n
    """
    need_event: bool = False

    def __init__(self,
                 relative_rect: pygame.Rect,
                 element_id: str = "none",
                 style_id: str = "",
                 element_types: str = ("element",),
                 parent: "Element" = None,
                 manager: "Manager" = None,
                 ):

        # parameters
        self.relative_rect: pygame.Rect = relative_rect
        self.manager: "Manager" = manager or UIState.current_manager

        # None checking
        if self.manager is None:
            raise UIError(
                f"Element manager can't be None. Make sure to give a valid manager parameter or set the correct current manager")

        self.parent: Element | "UIRoot" = parent or UIState.current_parent or self.manager.root
        self.manager._all_elements.append(self)

        if self.relative_rect is None:
            raise UIError(
                f"Element relative rect can't be None. Make sure to give a valid relative_rect parameter")
        self.relative_rect = pygame.Rect(relative_rect)

        if self.parent is None:
            raise UIError(
                "Element parent can't be None. Make sure to give a valid parent parameter or set the corrent current parent")

        # str attrs
        self.element_id: str = element_id
        self.object_id: int = id(self)
        self.style_id: str = (
            UIState.current_style_id+";" if UIState.current_style_id is not None else "") + style_id
        self.element_types: tuple[str] = element_types

        # attrs
        self.children: list[Element] = []
        self.ghost_element: Element | None = None
        self.ghost_offset: pygame.Vector2 = pygame.Vector2()
        self.element_surface: pygame.Surface = pygame.Surface(
            (max(self.relative_rect.w, 1), max(self.relative_rect.h, 1)), pygame.SRCALPHA)
        self.absolute_rect: pygame.Rect = self.relative_rect.copy()
        self.static_rect: pygame.Rect = self.relative_rect.copy()
        self.ignore_stack: bool = False
        self.ignore_scroll: bool = False
        self.ignore_raycast: bool = False
        self.can_destroy: bool = True
        
        self.z_index: int = common.Z_INDEXES["element"]
        self.scroll_offset: pygame.Vector2 = pygame.Vector2()
        self.render_offset: pygame.Vector2 = pygame.Vector2()
        self.attrs: dict[str] = {}
        self.resizers_size: int = 5
        self.resizers: tuple[str] = ()
        self.resize_min: common.Coordinate | None = (20, 20)
        self.resize_max: common.Coordinate | None = None
        self.playing_animations: list[UIPropertyAnim] = []
        self.tooltip: Element|None = None
        self._resizers_elements: dict[str, "Element"] = {}
        self._anchor_observers: list["Element"] = []
        self._anchors: dict[str, common.UIAnchorData | None] = dict.fromkeys(("left", "right", "top", "bottom", "centerx", "centery"), None)

        # obj attrs
        self.status: UIStatus = UIStatus(self)
        self.buffers: UIBuffers = UIBuffers(self)
        self.sounds: UISounds = UISounds(self)
        self._last_style: UIStyle = None
        self.style_group: UIStyleGroup = UIStyles.get_style_group(self)
        self.style: UIStyle = self.style_group.style
        self.masked_surface: pygame.Surface = pygame.Surface((max(1, self.relative_rect.w-self.style.stack.mask_padding*2),
                                                              max(1, self.relative_rect.h-self.style.stack.mask_padding*2)), pygame.SRCALPHA)

        # components
        self.components = ()
        self.callback_component: comps.UIComponent = comps.UIComponent(
            self, self.style_changed)
        self.bg: comps.UIBackgroundComp = comps.UIBackgroundComp(self)
        self.image: comps.UIImageComp = comps.UIImageComp(self)
        self.shape: comps.UIShapeComp = comps.UIShapeComp(self)
        self.text: comps.UITextComp = comps.UITextComp(self)
        self.icon: comps.UIIconComp = comps.UIIconComp(self)
        self.outline: comps.UIOutlineComp = comps.UIOutlineComp(self)

        self.components: tuple[comps.UIComponent] = (
            self.bg, self.image, self.shape, self.text, self.icon, self.outline
        )

        # setup
        if self.need_event:
            self.manager._event_callbacks.append(self)
        self._update_absolute_rect_pos()
        self.parent._add_child(self)
        self.init()

    # override
    def init(self):
        """Called at the very end of '__init__', overridable"""

    def on_logic(self):
        """Called on 'logic', overridable"""

    def on_render(self):
        """Called on 'render', overridable"""

    def on_destroy(self):
        """Called when the element is being destroyed, overridable"""

    def on_event(self, event: pygame.Event):
        """Called for every event if the need_event flag on the class is set to True, overridable"""

    def _refresh_stack(self):
        """Used by the stacks to organize children, overridable"""

    def size_changed(self):
        """Called when the size changes, overridable"""

    def style_changed(self):
        """Called when the style changes, overridable"""

    def position_changed(self):
        """Called when the position changes, overridable"""

    def build(self):
        """Called when the size or style changes, overridable"""

    # children
    def _add_child(self, element: "Element") -> typing.Self:
        if element not in self.children:
            self.children.append(element)
            self._refresh_stack()
            self.set_dirty()
        return self

    def remove_child(self, element: "Element") -> typing.Self:
        """Remove a child from the children, without destroying it"""
        if element in self.children:
            self.children.remove(element)
            self._refresh_stack()
            self.set_dirty()
        return self
    
    def remove_children(self, *elements: "Element") -> typing.Self:
        """Remove the specified children without destroying them"""
        for el in elements:
            if el in self.children:
                self.children.remove(el)
        self._refresh_stack()
        self.set_dirty()
        return self

    def destroy(self, force: bool = False):
        """Destroy the element and all its children if the 'can_destroy' flag is True or 'force' is True"""
        if not self.can_destroy and not force:
            return
        self.on_destroy()
        for obs in self._anchor_observers:
            obs._remove_dead_anchor(self)
        self.remove_anchors()
        if self.ghost_element is not None:
            self.ghost_element.destroy(True)
        self.parent.remove_child(self)
        for child in list(self.children):
            child.destroy(True)
        self.children.clear()
        if self in self.manager._all_elements:
            self.manager._all_elements.remove(self)
        if self in self.manager._event_callbacks:
            self.manager._event_callbacks.remove(self)
        del self

    def destroy_children(self) -> typing.Self:
        """Destroy all children of this element if the children have the 'can_destroy' flag set to True"""
        for child in list(self.children):
            child.destroy()
        self.set_dirty()
        return self

    def move_in_parent(self, places: int) -> typing.Self:
        """Move this element between the parent's children"""
        if len(self.parent.children) <= 1:
            return self
        new_idx = pygame.math.clamp(self.parent.children.index(
            self)+places, 0, len(self.parent.children)-1)
        self.parent.children.remove(self)
        self.parent.children.insert(new_idx, self)
        self.parent._refresh_stack()
        return self
    
    def call_in_children(self, function_name: str, *args, **kwargs) -> typing.Self:
        """Run the specified function name in all elements with the same args and kwargs"""
        for child in self.children:
            if hasattr(child, function_name):
                getattr(child, function_name)(*args, **kwargs)
        return self

    # flags
    def activate(self) -> typing.Self:
        """Activate the element (style will change on hover/press)"""
        self.status.active = True
        return self

    def deactivate(self) -> typing.Self:
        """Deactivate the element (style won't change on hover/press)"""
        self.status.active = False
        return self

    def show(self) -> typing.Self:
        """Set the status.visible flag to True, refresh the stack"""
        self.status.visible = True
        if not self.ignore_stack:
            self.parent._refresh_stack()
        self.set_dirty()
        return self

    def hide(self) -> typing.Self:
        """Set the status.visible flag to False, refresh the stack"""
        self.status.visible = False
        if self is self.manager.navigation.tabbed_element:
            self.manager.navigation.stop_navigating()
        if not self.ignore_stack:
            self.parent._refresh_stack()
        self.set_dirty()
        return self

    # dunder
    def __enter__(self) -> typing.Self:
        self._previous_parent = UIState.current_parent
        UIState.current_parent = self
        return self

    def __exit__(self, *args, **kwargs):
        UIState.current_parent = self._previous_parent
        self._refresh_stack()

    # get
    def can_render(self) -> bool:
        """Return whether the element can be rendered. If the element is not visible or outside of the parent's bounds False is returned. Can be useful not to waste performance on some operations"""
        return self.status.visible and self.absolute_rect.colliderect(self.parent.absolute_rect)
    
    def get_absolute_topleft(self) -> pygame.Vector2:
        """Return the topleft position from the origin of the window"""
        return pygame.Vector2(self.parent.get_absolute_topleft()+self.relative_rect.topleft)-(self.manager.root.scroll_offset if self.ignore_scroll else self.parent.scroll_offset)

    def get_attr(self, name: str):
        """Retrive a custom element attribute or None if it doesn't exist"""
        return self.attrs.get(name, None)

    def has_attr(self, name: str) -> bool:
        """Check if a custom element attribute exists"""
        return name in self.attrs
    
    def has_anchor(self, self_anchor: str):
        return self_anchor in self._anchors and self._anchors[self_anchor] is not None

    def get_index_in_parent(self) -> int:
        """Return the current index in the parent's children"""
        return self.parent.children.index(self)
    
    def get_destroyable_children(self) -> list["Element"]:
        """Return a list with the children this element can destroy (that have the can_destroy flag set to True)"""
        return [el for el in self.children if el.can_destroy]

    def is_stack(self) -> bool:
        """Return whether this is a stack element. Useful since properties like scrollbars are only accessible for stacks"""
        return False
    
    def is_root(self) -> bool:
        """Return whether this is the root element. Useful since root elements have very limited attributes"""
        return False
    
    def get_user_children(self) -> list["Element"]:
        """Return a list of children without elements added by guiscript like automatic scrollbars and resizers"""
        res = []
        for ch in self.children:
            if ch.has_attr("builtin"):
                continue
            res.append(ch)
        return res

    # navigation
    def can_navigate(self) -> bool:
        """Return whether the element can be navigated"""
        return self.status.can_navigate and self.status.visible

    def find_navigable_child(self) -> "Element":
        """Find a child that can be navigated between the element's children and their children"""
        if not self.can_navigate():
            return None
        for child in self.children:
            if child.can_navigate():
                return child
            else:
                their_child = child.find_navigable_child()
                if their_child is not None:
                    return their_child
        return None

    def has_navigable_child(self) -> bool:
        """Return whether at least one of the element's children can be navigated"""
        for child in self.children:
            if child.can_navigate():
                return True
        return False

    def navigable_children_count(self) -> bool:
        """Return how many of the element's children can be navigated"""
        count = 0
        for child in self.children:
            if child.can_navigate():
                count += 1
        return count

    # add
    def add_element_type(self, element_type: str) -> typing.Self:
        """Add one element type to the tuple and build a new style group"""
        self.element_types = (*self.element_types, element_type)
        self.set_style_group(UIStyles.get_style_group(self))
        return self

    def add_element_types(self, *element_types: str) -> typing.Self:
        """Add multiple element types to the tuple and build a new style group"""
        for et in element_types:
            self.add_element_type(et)
        return self
    
    def anchors_padding(self, padding: float, *skip_anchors: str) -> typing.Self:
        """Automatically set the offset of some anchors with the provided padding, inverting it for right and bottom. The specified anchors will be skipped"""
        for na, ad in self._anchors.items():
            if ad is None or na in skip_anchors:
                continue
            if na in ["top", "left"]:
                ad.offset = padding
            elif na in ["right", "bottom"]:
                ad.offset = -padding
        self._apply_anchors()
        return self
    
    # remove
    def remove_anchors(self, *skip_anchors: str) -> typing.Self:
        """Remove all anchors from the element except for anchors in skip"""
        for na, ad in list(self._anchors.items()):
            if ad is None or na in skip_anchors:
                continue
            ad.target._anchor_observers.remove(self)
            self._anchors[na] = None
        return self
    
    def remove_resizers(self, *resizers: str) -> typing.Self:
        """Remove the specified resizers"""
        old_resizers = self.resize_max
        resizers_list = list(self.resizers)
        for r in resizers:
            if r in resizers_list:
                resizers_list.remove(r)
        self.resizers = tuple(resizers_list)
        for name, rel in list(self._resizers_elements.items()):
            if name in old_resizers and name not in self.resizers:
                del self._resizers_elements[name]
                rel.destroy()
        return self

    def remove_animations(self) -> typing.Self:
        """Set all property animations of the element to a dead state"""
        for anim in list(self.playing_animations):
            anim.destroy()

    # set
    def set_children(self, children: list["Element"], destroy_old: bool = False) -> typing.Self:
        """Replace the current element's children with the specified ones. The old children will be destroyed following the destroy_old flag"""
        for ch in list(self.children):
            if ch not in children:
                if destroy_old:
                    ch.destroy()
                else:
                    self.remove_child(ch)
        for ch in children:
            if ch not in self.children:
                ch.set_parent(self)
        return self
        
    def set_user_children(self, children: list["Element"], destroy_old: bool = False) -> typing.Self:
        """Replace the current element's user children with the specified ones. The old children will be destroyed following the destroy_old flag"""
        user_children = self.get_user_children()
        for ch in user_children:
            if ch not in children:
                if destroy_old:
                    ch.destroy()
                else:
                    self.remove_child(ch)
        for ch in children:
            if ch not in user_children:
                ch.set_parent(self)
        return self
    
    def set_anchors(self, *target_selfanchor_targetanchor_offset: tuple[typing.Union[typing.Literal["parent"], None, "Element"], enums.Anchor, enums.Anchor, float]) -> typing.Self:
        """Sets multiple anchors. This element's set_anchor function will be called for each of the provided tuples which items should correspond to the arguments"""
        for tuple_data in target_selfanchor_targetanchor_offset:
            self.set_anchor(*tuple_data)
        return self
    
    def set_anchor(self, target: typing.Union[typing.Literal["parent"], None, "Element"], self_anchor: enums.Anchor = "none", target_anchor: enums.Anchor = "none", offset: float = 0) -> typing.Self:
        """
        Sets an anchor of the element. The side/position 'self_anchor' of this element will follow the side/position of 'target_anchor' of target. 
        If both are set to left, the left of this element will follow the left of the target. 
        NOTE: centerx and centery are not compatible with left, right and top, bottom respectively
        """
        self.set_ignore(stack=True)
        if self_anchor not in ["left", "right", "top", "bottom", "centerx", "centery"] or target_anchor not in ["left", "right", "top", "bottom", "centerx", "centery"]:
            raise UIError(
                f"Invalid anchor. Valid anchors are left, right, top, bottom, centerx, centery")
        if target is None:
            if self._anchors[self_anchor] is not None:
                self._anchors[self_anchor].target._anchor_observers.remove(
                    self)
            self._anchors[self_anchor] = None
            return self
        else:
            if self_anchor == "none" or target_anchor == "none":
                raise UIError(
                    f"If target is not None self and target anchors must not be 'none'")
        if target == "parent":
            target = self.parent
        if target.is_root():
            raise UIError("Anchor target cannot be root")
        data = common.UIAnchorData(target, self_anchor, target_anchor, offset)
        if self._anchors[self_anchor] is not None:
            self._anchors[self_anchor].target._anchor_observers.remove(self)
        self._anchors[self_anchor] = data
        target._anchor_observers.append(self)
        if (self._anchors["left"] is not None or self._anchors["right"] is not None) and self._anchors["centerx"] is not None:
            raise UIError(
                f"If the centerx anchor is set left and right anchors cannot be set too")
        if (self._anchors["top"] is not None or self._anchors["bottom"] is not None) and self._anchors["centery"] is not None:
            raise UIError(
                f"If the centery anchor is set top and bottom anchors cannot be set too")
        self._apply_anchors()
        return self

    def set_resizers(self, resizers: tuple[enums.Resizer], size: int = 5, min_size: common.Coordinate | None = (20, 20), max_size: common.Coordinate | None = None, style_id: str = "copy") -> typing.Self:
        """Set the specified resizers. The user will be able to resize the element on those points"""
        old_resizers = self.resizers
        self.resizers_size = size
        self.resizers = resizers
        self.resize_min = min_size
        self.resize_max = max_size
        for name, rel in list(self._resizers_elements.items()):
            if name in old_resizers:
                del self._resizers_elements[name]
                rel.destroy(True)
        for name in self.resizers:
            if name not in old_resizers:
                resizer = Element(pygame.Rect(0, 0, 1, 1), self.element_id+"_resizer",
                                  common.style_id_or_copy(self, style_id), ("element", "resizer"), self, self.manager).set_z_index(common.Z_INDEXES["resizer"]).set_ignore(True, True)
                if name in ["left", "right"]:
                    resizer.set_anchor("parent", name, name).set_anchor(
                        "parent", "centery", "centery")
                elif name in ["top", "bottom"]:
                    resizer.set_anchor("parent", name, name).set_anchor(
                        "parent", "centerx", "centerx")
                elif name.startswith("top"):
                    resizer.set_anchor("parent", "top", "top").set_anchor(
                        "parent", name.replace("top", ""), name.replace("top", ""))
                elif name.startswith("bottom"):
                    resizer.set_anchor("parent", "bottom", "bottom").set_anchor(
                        "parent", name.replace("bottom", ""), name.replace("bottom", ""))
                else:
                    common.warn(f"Could not properly anchor resizer with name '{name}'")
                resizer.set_attrs(resizer_name=name, builtin=True)
                self._resizers_elements[name] = resizer
        self._update_resizers_size()
        return self

    def set_index_in_parent(self, index: int) -> typing.Self:
        """Set the current index in the parent's children"""
        self.parent.children.remove(self)
        self.parent.children.insert(pygame.math.clamp(
            index, 0, len(self.parent.children)), self)
        self.parent._refresh_stack()
        return self

    def set_ignore(self, stack: bool | None = None, scroll: bool | None = None, raycast: bool | None = None) -> typing.Self:
        """Set the 'ignore_stack' and 'ignore_scroll' flags"""
        self.ignore_stack = stack if stack is not None else self.ignore_stack
        self.ignore_scroll = scroll if scroll is not None else self.ignore_scroll
        self.ignore_raycast = raycast if raycast is not None else self.ignore_raycast
        return self

    def set_dirty(self, dirty: bool = True) -> typing.Self:
        """Change the dirty flag, usually to True. This will cause the element to re-render"""
        if dirty == self.status.dirty:
            return self
        self.status.dirty = dirty
        self.parent.set_dirty()
        return self

    def set_can_destroy(self, can_destroy: bool) -> typing.Self:
        """Set the 'can_destroy' flag. If it is False, destroy() won't work"""
        self.can_destroy = can_destroy
        return self

    def set_z_index(self, z_index: int) -> typing.Self:
        """Set the Z index used for interaction and rendering"""
        self.z_index = z_index
        self.set_dirty()
        return self

    def set_attr(self, name: str, value) -> typing.Self:
        """Set a custom element attribute"""
        self.attrs[name] = value
        return self

    def set_attrs(self, **names_values) -> typing.Self:
        """Set multiple custom element attributes using kwargs"""
        for name, val in names_values.items():
            self.attrs[name] = val
        return self

    def set_absolute_pos(self, position: common.Coordinate, apply_anchors: bool = True) -> typing.Self:
        """Set the topleft position from the origin of the window"""
        old = self.relative_rect.topleft
        self.relative_rect.topleft = position-self.parent.get_absolute_topleft()
        if old == self.relative_rect.topleft:
            return self

        self._update_absolute_rect_pos()
        for comp in self.components:
            comp._position_changed()
        self.position_changed()
        self.status.invoke_callbacks("on_position_change")
        for obs in self._anchor_observers:
            obs._apply_anchors()
        if apply_anchors: self._apply_anchors()
        return self

    def set_relative_pos(self, position: common.Coordinate) -> typing.Self:
        """Set the relative position to the parent"""
        if self.relative_rect.topleft == (int(position[0]), int(position[1])):
            return self

        self.relative_rect.topleft = position
        self._update_absolute_rect_pos()
        for comp in self.components:
            comp._position_changed()
        self.position_changed()
        self.status.invoke_callbacks("on_position_change")
        for obs in self._anchor_observers:
            obs._apply_anchors()
        self._apply_anchors()
        return self

    def set_size(self, size: common.Coordinate, propagate_up: bool = False, apply_anchors: bool = True, refresh_stack: bool = True) -> typing.Self:
        """Set the element's size"""
        s0, s1 = int(size[0]), int(size[1])
        if self.relative_rect.size == (s0, s1):
            return self

        self.relative_rect.size = (max(1, s0), max(1, s1))
        self._update_absolute_rect_size(propagate_up)
        self._update_surface_size()
        for comp in self.components:
            comp._size_changed()
        self.size_changed()
        self.build()
        self.status.invoke_callbacks("on_size_change", "on_build")
        self._update_resizers_size()
        
        for obs in self._anchor_observers:
            obs._apply_anchors()
        if apply_anchors:
            self._apply_anchors()
        if refresh_stack: self._refresh_stack()
        return self

    def set_width(self, width: int) -> typing.Self:
        """Set the element's width"""
        return self.set_size((width, self.relative_rect.h))

    def set_height(self, height: int) -> typing.Self:
        """Set the element's height"""
        return self.set_size((self.relative_rect.w, height))

    def set_relative_size(self, relative_size: common.Coordinate) -> typing.Self:
        """Set the element's size multiplying the parent's one with the provided values in range 0-1"""
        return self.set_size((self.parent.relative_rect.w*relative_size[0], self.parent.relative_rect.h*relative_size[1]))

    def set_relative_width(self, relative_width: float) -> typing.Self:
        """Set the element's width multiplying the parent's one with the provided value in range 0-1"""
        return self.set_size((self.parent.relative_rect.w*relative_width, self.relative_rect.h))

    def set_relative_height(self, relative_height: float) -> typing.Self:
        """Set the element's height multiplying the parent's one with the provided value in range 0-1"""
        return self.set_size((self.relative_rect.w, self.parent.relative_rect.h*relative_height))

    def set_style_group(self, style_group: UIStyleGroup) -> typing.Self:
        """Manually set the style group of the element (not recommended)"""
        self.style_group = style_group
        self.style = self.style_group.style
        for comp in self.components:
            comp._style_changed()
        self.style_changed()
        self.build()
        self.status.invoke_callbacks("on_style_change", "on_build")
        self.set_dirty()
        return self

    def set_style_id(self, style_id: str) -> typing.Self:
        """Set the style id of the element and build a new style group"""
        self.style_id = style_id
        self.set_style_group(UIStyles.get_style_group(self))
        return self

    def set_element_types(self, element_types: tuple[str]) -> typing.Self:
        """Set the element types of the element and build a new style group"""
        self.element_types = element_types
        self.set_style_group(UIStyles.get_style_group(self))
        return self
    
    def set_element_id(self, element_id: str) -> typing.Self:
        """Set the element id of the element and build a new style group"""
        self.element_id = element_id
        self.set_style_group(UIStyle.get_style_group(self))
        return self
    
    def set_parent(self, parent: typing.Union["Element", None]) -> typing.Self:
        """Set the element's parent. If the provided parent is None, the root will be used"""
        if parent is None:
            parent = self.manager.root
        if parent is self.parent:
            return self
        self.parent.remove_child(self)
        self.parent = parent
        self.parent._add_child(self)
        return self

    def set_tooltip(self, title: str, description: str = "", width: int = 200, height: int = 200, title_h: int = 40, style_id: str = "copy", title_style_id: str = "copy", descr_style_id: str = "copy") -> typing.Self:
        """Build a new tooltip object with the provided settings and register it"""
        tooltip_cont = Element(pygame.Rect(0, 0, width, height),
                               self.element_id+"tooltip_container",
                               common.style_id_or_copy(self, style_id),
                               ("element", "tooltip", "tooltip_container"),
                               self.manager.root, self.manager).set_z_index(common.Z_INDEXES["tooltip"])
        if title:
            Element(pygame.Rect(0, 0, width, title_h),
                    self.element_id+"tooltip_title",
                    common.style_id_or_copy(tooltip_cont, title_style_id),
                    ("element", "tooltip", "text",
                     "tooltip_text", "tooltip_title"),
                    tooltip_cont, self.manager).text.set_text(title).element
        Element(pygame.Rect(0, title_h if title else 0, width, height-title_h if title else height),
                self.element_id+"tooltip_description",
                common.style_id_or_copy(tooltip_cont, descr_style_id),
                ("element", "tooltip", "text",
                 "tooltip_text", "tooltip_description"),
                tooltip_cont, self.manager).text.set_text(description).element
        self.tooltip = tooltip_cont
        tooltip_cont.hide()
        Tooltips.register(tooltip_cont, self)
        return self

    def set_custom_tooltip(self, tooltip: "Element") -> typing.Self:
        """Register a given tooltip object to appear when hovering this element"""
        if tooltip.z_index < common.Z_INDEXES["tooltip"]:
            tooltip.set_z_index(common.Z_INDEXES["tooltip"])
        tooltip.hide()
        self.tooltip = tooltip
        Tooltips.register(tooltip, self)
        return self

    def set_ghost(self, relative_rect: pygame.Rect, offset: common.Coordinate = (0, 0)) -> typing.Self:
        """Create an element that will be invisible that this element will follow while also setting the 'ignore_stack' flag to True"""
        if self.ghost_element is not None:
            self.ghost_element.destroy()
            self.ghost_element = None
        self.set_ignore(stack=True)
        self.ghost_element = Element(relative_rect, self.element_id+"_ghost", "invisible",
                                     ("element", "ghost"), self.parent, self.manager).set_z_index(common.Z_INDEXES["ghost"])
        self.ghost_offset = pygame.Vector2(offset)
        return self

    def set_render_offset(self, render_offset: common.Coordinate) -> typing.Self:
        """Set the offset where to render element onto the parent"""
        self.render_offset = pygame.Vector2(render_offset)
        self.set_dirty()
        return self
    
    def build_components(self) -> typing.Self:
        """Manually build the rendering components"""
        for comp in self.components:
            comp._build(self.style)
        return self

    # animation
    def animate_x(self, increase: float, duration_ms: int, repeat_mode: AnimRepeatMode = AnimRepeatMode.once,
                  ease_func_name: AnimEaseFunc = AnimEaseFunc.ease_in) -> typing.Self:
        """Create a new property animation for the x coordinate"""
        UIPropertyAnim(self, AnimPropertyType.x, increase,
                       duration_ms, repeat_mode, ease_func_name)
        return self

    def animate_offset_x(self, increase: float, duration_ms: int, repeat_mode: AnimRepeatMode = AnimRepeatMode.once,
                         ease_func_name: AnimEaseFunc = AnimEaseFunc.ease_in) -> typing.Self:
        """Create a new property animation for the x render offset coordinate"""
        UIPropertyAnim(self, AnimPropertyType.render_x, increase,
                       duration_ms, repeat_mode, ease_func_name)
        return self

    def animate_y(self, increase: float, duration_ms: int, repeat_mode: AnimRepeatMode = AnimRepeatMode.once,
                  ease_func_name: AnimEaseFunc = AnimEaseFunc.ease_in) -> typing.Self:
        """Create a new property animation for the y coordinate"""
        UIPropertyAnim(self, AnimPropertyType.y, increase,
                       duration_ms, repeat_mode, ease_func_name)
        return self

    def animate_offset_y(self, increase: float, duration_ms: int, repeat_mode: AnimRepeatMode = AnimRepeatMode.once,
                         ease_func_name: AnimEaseFunc = AnimEaseFunc.ease_in) -> typing.Self:
        """Create a new property animation for the y render offset coordinate"""
        UIPropertyAnim(self, AnimPropertyType.render_y, increase,
                       duration_ms, repeat_mode, ease_func_name)
        return self

    def animate_xy(self, increase: float, duration_ms: int, repeat_mode: AnimRepeatMode = AnimRepeatMode.once,
                   ease_func_name: AnimEaseFunc = AnimEaseFunc.ease_in) -> typing.Self:
        """Create a new property animation for the x and y coordinates"""
        UIPropertyAnim(self, AnimPropertyType.x, increase,
                       duration_ms, repeat_mode, ease_func_name)
        UIPropertyAnim(self, AnimPropertyType.y, increase,
                       duration_ms, repeat_mode, ease_func_name)
        return self

    def animate_offset_xy(self, increase: float, duration_ms: int, repeat_mode: AnimRepeatMode = AnimRepeatMode.once,
                          ease_func_name: AnimEaseFunc = AnimEaseFunc.ease_in) -> typing.Self:
        """Create a new property animation for the x and y render offset coordinates"""
        UIPropertyAnim(self, AnimPropertyType.render_x, increase,
                       duration_ms, repeat_mode, ease_func_name)
        UIPropertyAnim(self, AnimPropertyType.render_y, increase,
                       duration_ms, repeat_mode, ease_func_name)
        return self

    def animate_w(self, increase: float, duration_ms: int, repeat_mode: AnimRepeatMode = AnimRepeatMode.once,
                  ease_func_name: AnimEaseFunc = AnimEaseFunc.ease_in) -> typing.Self:
        """Create a new property animation for the width"""
        UIPropertyAnim(self, AnimPropertyType.width, increase,
                       duration_ms, repeat_mode, ease_func_name)
        return self

    def animate_h(self, increase: float, duration_ms: int, repeat_mode: AnimRepeatMode = AnimRepeatMode.once,
                  ease_func_name: AnimEaseFunc = AnimEaseFunc.ease_in) -> typing.Self:
        """Create a new property animation for the height"""
        UIPropertyAnim(self, AnimPropertyType.height, increase,
                       duration_ms, repeat_mode, ease_func_name)
        return self

    def animate_wh(self, increase: float, duration_ms: int, repeat_mode: AnimRepeatMode = AnimRepeatMode.once,
                   ease_func_name: AnimEaseFunc = AnimEaseFunc.ease_in) -> typing.Self:
        """Create a new property animation for the width and height"""
        UIPropertyAnim(self, AnimPropertyType.width, increase,
                       duration_ms, repeat_mode, ease_func_name)
        UIPropertyAnim(self, AnimPropertyType.height, increase,
                       duration_ms, repeat_mode, ease_func_name)
        return self

    def animate_x_to(self, value: float, duration_ms: int, repeat_mode: AnimRepeatMode = AnimRepeatMode.once,
                     ease_func_name: AnimEaseFunc = AnimEaseFunc.ease_in) -> typing.Self:
        """Create a new property animation for the x coordinate setting the increase relative to the current value and end value"""
        return self.animate_x(value-self.relative_rect.x, duration_ms, repeat_mode, ease_func_name)

    def animate_offset_x_to(self, value: float, duration_ms: int, repeat_mode: AnimRepeatMode = AnimRepeatMode.once,
                            ease_func_name: AnimEaseFunc = AnimEaseFunc.ease_in) -> typing.Self:
        """Create a new property animation for the x render offset coordinate setting the increase relative to the current value and end value"""
        return self.animate_offset_x(value-self.render_offset.x, duration_ms, repeat_mode, ease_func_name)

    def animate_y_to(self, value: float, duration_ms: int, repeat_mode: AnimRepeatMode = AnimRepeatMode.once,
                     ease_func_name: AnimEaseFunc = AnimEaseFunc.ease_in) -> typing.Self:
        """Create a new property animation for the y coordinate setting the increase relative to the current value and end value"""
        return self.animate_y(value-self.relative_rect.y, duration_ms, repeat_mode, ease_func_name)

    def animate_offset_y_to(self, value: float, duration_ms: int, repeat_mode: AnimRepeatMode = AnimRepeatMode.once,
                            ease_func_name: AnimEaseFunc = AnimEaseFunc.ease_in) -> typing.Self:
        """Create a new property animation for the y render offset coordinate setting the increase relative to the current value and end value"""
        return self.animate_offset_y(value-self.render_offset.y, duration_ms, repeat_mode, ease_func_name)

    def animate_xy_to(self, value: float, duration_ms: int, repeat_mode: AnimRepeatMode = AnimRepeatMode.once,
                      ease_func_name: AnimEaseFunc = AnimEaseFunc.ease_in) -> typing.Self:
        """Create a new property animation for the x and y coordinates setting the increase relative to the current value and end value"""
        self.animate_x(value-self.relative_rect.x, duration_ms,
                       repeat_mode, ease_func_name)
        self.animate_y(value-self.relative_rect.y, duration_ms,
                       repeat_mode, ease_func_name)
        return self

    def animate_offset_xy_to(self, value: float, duration_ms: int, repeat_mode: AnimRepeatMode = AnimRepeatMode.once,
                             ease_func_name: AnimEaseFunc = AnimEaseFunc.ease_in) -> typing.Self:
        """Create a new property animation for the x and y render offset coordinates setting the increase relative to the current value and end value"""
        self.animate_offset_x(value-self.render_offset.x, duration_ms,
                              repeat_mode, ease_func_name)
        self.animate_offset_y(value-self.render_offset.y, duration_ms,
                              repeat_mode, ease_func_name)
        return self

    def animate_w_to(self, value: float, duration_ms: int, repeat_mode: AnimRepeatMode = AnimRepeatMode.once,
                     ease_func_name: AnimEaseFunc = AnimEaseFunc.ease_in) -> typing.Self:
        """Create a new property animation for the width setting the increase relative to the current value and end value"""
        return self.animate_w(value-self.relative_rect.w, duration_ms, repeat_mode, ease_func_name)

    def animate_h_to(self, value: float, duration_ms: int, repeat_mode: AnimRepeatMode = AnimRepeatMode.once,
                     ease_func_name: AnimEaseFunc = AnimEaseFunc.ease_in) -> typing.Self:
        """Create a new property animation for the height setting the increase relative to the current value and end value"""
        return self.animate_h(value-self.relative_rect.h, duration_ms, repeat_mode, ease_func_name)

    def animate_wh_to(self, value: float, duration_ms: int, repeat_mode: AnimRepeatMode = AnimRepeatMode.once,
                      ease_func_name: AnimEaseFunc = AnimEaseFunc.ease_in) -> typing.Self:
        """Create a new property animation for the width and height setting the increase relative to the current value and end value"""
        self.animate_w(value-self.relative_rect.w, duration_ms,
                       repeat_mode, ease_func_name)
        self.animate_h(value-self.relative_rect.h, duration_ms,
                       repeat_mode, ease_func_name)
        return self

    # update
    def _update_absolute_rect_pos(self):
        self.absolute_rect.topleft = self.get_absolute_topleft()
        self.static_rect.topleft = (0, 0)
        for child in self.children:
            child._update_absolute_rect_pos()
        self.set_dirty()

    def _update_absolute_rect_size(self, propagate_up: bool = True):
        self.absolute_rect.size = self.relative_rect.size
        self.static_rect.size = self.relative_rect.size
        if propagate_up and not self.ignore_stack:
            self.parent._refresh_stack()

    def _update_surface_size(self):
        if self.element_surface.get_size() != self.relative_rect.size:
            self.element_surface = pygame.Surface(
                (max(self.relative_rect.w, 1), max(self.relative_rect.h, 1)), pygame.SRCALPHA)
            self.masked_surface: pygame.Surface = pygame.Surface((max(1, self.relative_rect.w-self.style.stack.mask_padding*2),
                                                                  max(1, self.relative_rect.h-self.style.stack.mask_padding*2)), pygame.SRCALPHA)
        self.set_dirty()

    def _update_style(self):
        self.set_dirty()
        self._refresh_stack()
        self.style_changed()
        self.build()
        if not self.ignore_stack:
            self.parent._refresh_stack()
        for comp in self.components:
            comp._build(self.style)
        self.style._enter()
        self.status.invoke_callbacks(
            "on_style_change", "on_build")
        self._update_resizers_size()
        self._apply_anchors()

    def _update_resizers_size(self):
        for name, rel in self._resizers_elements.items():
            if name == "top" or name == "bottom":
                rel.set_size(
                    (self.relative_rect.w-self.resizers_size*2, self.resizers_size))
            elif name == "left" or name == "right":
                rel.set_size(
                    (self.resizers_size, self.relative_rect.h-self.resizers_size*2))
            else:
                rel.set_size((self.resizers_size*2, self.resizers_size*2))
                
    def _remove_dead_anchor(self, dead_element: "Element"):
        for an, ad in list(self._anchors.items()):
            if ad is not None and ad.target is dead_element:
                self._anchors[an] = None
                break
            
    def _first_frame(self):
        self._refresh_stack()
        self.build()
        self.position_changed()
        self.status.invoke_callback("on_first_frame", "on_position_change", "on_build")
        
    def _apply_anchors(self):
        if all([x is None for x in self._anchors.values()]):
            return
        temp_r = self.absolute_rect.copy()
        if (cxad := self._anchors["centerx"]) is not None:
            temp_r.centerx = getattr(
                cxad.target.absolute_rect, cxad.target_anchor)+cxad.offset
        else:
            left, right = None, None
            if (lad := self._anchors["left"]) is not None:
                left = getattr(lad.target.absolute_rect,
                               lad.target_anchor)+lad.offset
            if (rad := self._anchors["right"]) is not None:
                right = getattr(rad.target.absolute_rect,
                                rad.target_anchor)+rad.offset
            if right is None and left is not None:
                right = left+self.absolute_rect.w
            elif left is None and right is not None:
                left = right-self.absolute_rect.w
            elif left is None and right is None:
                left, right = self.absolute_rect.left, self.absolute_rect.right
            if right <= left:
                right = left+1
            temp_r.left = left
            temp_r.width = right-left
        if (cyad := self._anchors["centery"]) is not None:
            temp_r.centery = getattr(
                cyad.target.absolute_rect, cyad.target_anchor)+cyad.offset
        else:
            top, bottom = None, None
            if (tad := self._anchors["top"]) is not None:
                top = getattr(tad.target.absolute_rect,
                              tad.target_anchor)+tad.offset
            if (bad := self._anchors["bottom"]) is not None:
                bottom = getattr(bad.target.absolute_rect,
                                 bad.target_anchor)+bad.offset
            if bottom is None and top is not None:
                bottom = top+self.absolute_rect.h
            elif top is None and bottom is not None:
                top = bottom-self.absolute_rect.h
            elif top is None and bottom is None:
                top, bottom = self.absolute_rect.top, self.absolute_rect.bottom
            if bottom <= top:
                bottom = top+1
            temp_r.top = top
            temp_r.height = bottom-top
        self.set_size(temp_r.size, apply_anchors=False)
        self.set_absolute_pos(temp_r.topleft, apply_anchors=False)
        
    # runtime
    def _logic(self):
        if not self.status.visible:
            return
        if self.ghost_element is not None:
            self.set_relative_pos((self.ghost_element.relative_rect.centerx-self.relative_rect.w // 2+self.ghost_offset.x,
                                   self.ghost_element.relative_rect.centery-self.relative_rect.h//2+self.ghost_offset.y))
        for child in sorted(self.children, key=lambda el: el.z_index):
            child._logic()
            
        style: UIStyle = None
        if not self.status.active:
            style = self.style_group.style
        elif self.status.pressed or self.status.selected:
            style = self.style_group.press_style
        elif self.status.hovered:
            style = self.style_group.hover_style
        else:
            style = self.style_group.style
        if style is not self._last_style:
            self.style = style
            self._update_style()
            self._last_style = style
        
        self.style._logic()
        if self.style.dirty:
            for comp in self.components:
                comp._build(self.style)
            self.style.dirty = False
            self.set_dirty()
            self.style_changed()
            self.build()
            self.status.invoke_callbacks("on_style_change", "on_build")
            
        if len(self._resizers_elements) > 0 and UIState.mouse_rel.length() > 0:
            for name, rel in self._resizers_elements.items():
                if rel.status.pressed:
                    xi = yi = pxi = pyi = 0
                    if "left" in name:
                        xi = -UIState.mouse_rel.x
                        pxi = UIState.mouse_rel.x
                    elif "right" in name:
                        xi = UIState.mouse_rel.x
                    if "top" in name:
                        yi = -UIState.mouse_rel.y
                        pyi = UIState.mouse_rel.y
                    elif "bottom" in name:
                        yi = UIState.mouse_rel.y
                    rmn, rmx = self.resize_min, self.resize_max
                    if rmn is None:
                        rmn = (0, 0)
                    if rmx is None:
                        rmx = (float("inf"), float("inf"))
                    old_x, old_y = self.relative_rect.size
                    new_size = (pygame.math.clamp(self.relative_rect.w+xi, rmn[0], rmx[0]),
                                   pygame.math.clamp(self.relative_rect.h+yi, rmn[1], rmx[1]))
                    if old_x == new_size[0]:
                        pxi = 0
                    if old_y == new_size[1]:
                        pyi = 0
                    if pxi != 0 or pyi != 0:
                        self.set_relative_pos(
                            (self.relative_rect.x+pxi, self.relative_rect.y+pyi))
                    self.set_size(new_size, True)
                    self.status.invoke_callback("on_resize")
                    events._post_base_event(events.RESIZE, self)
        if self.status.can_drag and self.status.pressed:
            self.status.dragging = True
            if UIState.mouse_rel.length() > 0:
                self.set_relative_pos((self.relative_rect.x+UIState.mouse_rel.x, self.relative_rect.y+UIState.mouse_rel.y))
                self.status.invoke_callback("on_drag")
                events._post_base_event(events.DRAG, self)
        else:
            self.status.dragging = False

        self.on_logic()

    def _render(self, parent_mask_padding: int = 0, force_render: bool = False, fake: bool = False):
        if not self.status.visible or (not self.status.dirty and not force_render):
            return
        if not self.absolute_rect.colliderect(self.parent.absolute_rect):
            return
        if fake:
            self.manager._last_rendered = self
            for child in self.children:
                child._render(fake=True)
            return

        if self.status.dirty:
            mask_padding = self.style.stack.mask_padding
            self.manager._last_rendered = self
            self.element_surface.fill(0)
            if mask_padding > 0:
                self.masked_surface.fill(0)

            for i, comp in enumerate(self.components):
                if i == len(self.components)-1:
                    for child in sorted(self.children, key=lambda el: el.z_index):
                        child._render(mask_padding, True)
                    if mask_padding > 0:
                        self.element_surface.blit(
                            self.masked_surface, (mask_padding, mask_padding))
                if comp.enabled:
                    comp._render()

            self.on_render()
        else:
            self.manager._last_rendered = self
            for child in self.children:
                child._render(fake=True)
        if parent_mask_padding <= 0:
            self.parent.element_surface.blit(self.element_surface, self.relative_rect.topleft -
                                             (self.manager.root.scroll_offset if self.ignore_scroll else self.parent.scroll_offset)+self.render_offset)
        else:
            self.parent.masked_surface.blit(self.element_surface, self.relative_rect.topleft -
                                            (pygame.Vector2(parent_mask_padding, parent_mask_padding)) -
                                            (self.manager.root.scroll_offset if self.ignore_scroll else self.parent.scroll_offset)+self.render_offset)
        self.status.dirty = False
