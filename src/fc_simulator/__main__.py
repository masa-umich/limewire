import asyncio

from fc_simulator import run_server


def main():
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        print("Ctrl+C received.")
        exit(0)


if __name__ == "__main__":
    main()
