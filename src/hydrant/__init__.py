from nicegui import ui

from .hydrant import main_page


def main():
    print("! HYDRANT RUNNING !")
    ui.run(main_page, show=False, reload=False)


if __name__ == "__main__":
    main()
