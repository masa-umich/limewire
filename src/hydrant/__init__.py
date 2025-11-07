from nicegui import ui
from .hydrant import Hydrant

def main():
    print("! HYDRANT RUNNING !")

    hydrant = Hydrant()
    hydrant.main_page()

    ui.run(hydrant.main_page, show=False, reload=False)

if __name__ == "__main__":
    main()