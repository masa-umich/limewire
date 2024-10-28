# Limewire

Limewire is a driver that facilitates communication between Synnax and
Limelight. Check out the [Limewire Design
Doc](https://docs.google.com/document/d/1Ccmjck5NHinmJLGH1tcoJ1EP9xZHQlAl20x2YuC15tI/edit?usp=sharing)
for all relevant information.

Project Lead: Rohan Satapathy

## Installation

How you install Limewire will depend on whether you're installing it in a
development environment or on the DAQ PC. 

### Development Installation

1. Make sure you have Python 3.12 or greater installed.

2. Install [Poetry](https://python-poetry.org/docs/), a dependency manager
   and virtual environment manager for Python projects. 

   > [!NOTE]
   > I highly recommend using the `pipx` installation method. `pipx` is a
   > Python tool that is used to install packages that expose a command-line
   > tool (such as Poetry) inside an isolated virtual environment. If this
   > doesn't work for you, feel free to contact me (Rohan Satapathy) on
   > Slack or use whichever installation method works for you.

3. Clone the repository and `cd` into the project directory.
   
   ```shell
   git clone https://github.com/masa-umich/limewire.git
   cd limewire
   ```

4. Install the project dependencies.

   ```shell
   poetry install
   ```

5. To run Limewire or the FC Simulator, run the following commands.

   ```shell
   # Run this once to enter the virtual environment
   poetry shell

   python -m limewire [IP]:[port]
   # OR
   python -m fc_simulator [IP]:[port]
   ```

6. Install [Ruff](https://github.com/astral-sh/ruff), a linter and code
   formatter for Python projects. If you use VS Code, you can install the
   [VS Code Ruff Extension](https://marketplace.visualstudio.com/items?itemName=charliermarsh.ruff).
   
   All code submitted to this project should be formatted using Ruff before
   being merged into `main`. An easy way to do this is configure your editor
   to enable "Format on Save". 

### DAQ PC Installation

Limewire is installed on the DAQ PC using `pipx` because it installs
Limewire in a virtual environment while globally exposing the `limewire`
command-line entry point. To download the latest version from GitHub, use
the following command.

```
pipx reinstall limewire
```

Then, run Limewire.

```
limewire [IP]:[port]
```

## Project Structure

This repository currently contains three packages in the `src` directory:

- `limewire`: The Limewire driver, a TCP client that runs on the DAQ
  PC and process telemetry data from the flight computer.
- `fc_simulator`: The Flight Computer Simulator, a TCP server that acts
  as a stand-in for the Flight Computer while its Ethernet issues are being
  debugged, enabling testing of Limewire.
- `packets`: A set of utility classes that represent different types of 
  packets within the Limelight Packet Structure.

At the moment, the FC Simulator is configured to send as many telemetry
packets as possible to Limewire for a period of 10 seconds, then report the
number of packets successfully transmitted. 

To test Limewire, you need to run the FC Simulator on your development
machine, then run Limewire on the DAQ PC. To do so, use the following
instructions.

1. Make sure you're connected to the University of Michigan WiFi. If you
   aren't on campus, you can use the 
   [UMVPN](https://its.umich.edu/enterprise/wifi-networks/vpn/getting-started)
   service. If you need help getting this set up properly, contact Rohan
   Satapathy on Slack.
   
2. Find your public IP address. The method to do this varies based on your
   operating system, but you should end up with a IPv4 address that looks
   like `35.X.X.X`. On macOS, the command to do this is `ipconfig getifaddr
   en0`.

3. Open a new terminal window and start the FC Simulator. Make sure you've
   activated the virtual environment with `poetry shell` first.

   ```shell
   python -m fc_simulator [public-ip-address]:8888
   ```

   You might receive a pop-up asking if you want to allow Python to accept
   incoming network connections. Make sure this option is enabled.

4. Use `ssh` to access the DAQ PC.

   ```shell
   ssh [username]@[daq-pc-ip-address]
   ```
   To get the username and IP address of the DAQ PC, contact Rohan Satapathy
   on Slack.

5. If Limewire has been updated on GitHub, install the latest version on the
   DAQ PC.

   ```shell
   pipx reinstall limewire
   ```

6. Run Limewire.
   
   ```shell
   limewire [public-ip-address]:8888
   ```

If you would like to test Limewire locally, use the IP address `127.0.0.1`
in place of `[public-ip-address]` and run Limewire using `python -m
limewire 127.0.0.1:8888` on your local machine.
