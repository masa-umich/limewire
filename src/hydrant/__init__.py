# Just run the module when imported
from . import hydrant
from nicegui import ui


def main():
    print("! HYDRANT RUNNING !")
    ui.run(show=False, reload=False)