from nicegui import ui

def setup():
    with ui.card():
        ui.label('Frontend')
        ui.button('Say hi', on_click=lambda: ui.notify('Hi from UI!'))
    
def run():
    print("Running...")
    ui.run(show=False, reload=False) # Reload must be disabled to run as a module