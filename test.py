import pygame
import sys, os
import src.guiscript as guis
from pygame import Rect as rect

pygame.Rect()
W, H = 1200, 800
pygame.init()
screen = pygame.display.set_mode((W, H), pygame.RESIZABLE)
clock = pygame.Clock()

test_surf = pygame.image.load("tests/test.jpg").convert()
menu_surf = pygame.transform.scale_by(pygame.image.load("tests/menu.png").convert_alpha(), 3)


manager = guis.Manager(screen, True, ["tests/example.gss"])
surfaces = [test_surf, menu_surf, test_surf]

def open_modal():
    modal.show()
    
def close_modal():
    modal.hide()

with guis.column((W, H), False) as MAIN:
    with guis.VStack(guis.SizeR(600,700), style_id="no_scroll").set_resizers(guis.ALL_RESIZERS):
        el = guis.Entry(guis.SizeR(500,80), '<c fg="green">ciao!!</c>', settings=guis.EntrySettings(inner_style_id="richtext")).set_resizers(guis.ALL_RESIZERS)
        tb = guis.Textbox(guis.SizeR(500,300), "ciaooo\ncome\nstaiii", settings=guis.TextboxSettings(inner_style_id="richtext")).set_resizers(guis.ALL_RESIZERS)
        t=guis.Text("ABC\nDEF\nPKM", guis.SizeR(200,100), style_id="cursor")
        t.text.set_cursor_index(1,1)
        with guis.row((0, 150)):
            with guis.column((200,0)):
                with guis.row((0,50)):
                    c1 = guis.Checkbox(guis.SizeR(40,40))
                    guis.Text("Check 1", guis.ZeroR(), style_id="fill")
                with guis.row((0,50)):
                    c2 = guis.Checkbox(guis.SizeR(40,40))
                    guis.Text("Check 2", guis.ZeroR(), style_id="fill") 
            with guis.column((200,0)):
                guis.Button(f"OPEN", guis.SizeR(200,60)).status.add_listener("on_click", open_modal)
            
        guis.bind_one_selected_only((c1, c2), True)

modal_element:guis.Window=guis.Window(guis.SizeR(300,300), "Modal Thing",
                                 settings=guis.WindowSettings(have_close_button=False)).status.set_drag(False).element.set_ignore(False, False)
with modal_element.enter():
    guis.Button(f"HIDE", guis.SizeR(200,60)).status.add_listener("on_click", close_modal)
    
modal = guis.ModalContainer(modal_element)
          
while True:   
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        elif event.type == pygame.VIDEORESIZE:
            W, H = event.w, event.h
            screen = pygame.display.set_mode((W, H), pygame.RESIZABLE)
            manager.set_screen_surface(screen)
            MAIN.set_size((W, H))
        elif event.type == guis.TEXTBOX_CHANGE:
            if True:
                txt = event.text
                event.textbox.set_text(txt.replace("ciao", f'<b>ciao</b>'))
                event.textbox.focus()
            
        manager.event(event)
        
    screen.fill("black")

    manager.logic()
    guis.static_logic(1)
    manager.render()

    clock.tick_busy_loop(0)
    pygame.display.flip()
    pygame.display.set_caption(f"{clock.get_fps():.0f} FPS")
