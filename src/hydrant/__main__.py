
from .hydrant import setup, run

if __name__ in {"__main__", "__mp_main__"}:
    setup()
    run()