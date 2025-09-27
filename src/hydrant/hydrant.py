from nicegui import ui

def setup():
    with ui.card():
        ui.label('Frontend')
        ui.button('Hello World', on_click=lambda: print("Hello, world!"))
    
def run():
    print("Running...")
    ui.run(show=False, reload=False) # Reload must be disabled to run as a module