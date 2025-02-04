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

2. Install [uv](https://docs.astral.sh/uv/getting-started/installation/), a
   project manager for Python. If you're on macOS, you can install `uv`
   with Homebrew using `brew install uv`.

3. Clone the repository and `cd` into the project directory.
   
   ```shell
   git clone https://github.com/masa-umich/limewire.git
   cd limewire
   ```

4. Install the project dependencies.

   ```shell
   uv sync
   ```

5. Install [Ruff](https://github.com/astral-sh/ruff), a linter and code
   formatter for Python projects. If you use VS Code, you can install the
   [VS Code Ruff Extension](https://marketplace.visualstudio.com/items?itemName=charliermarsh.ruff).
   
   All code submitted to this project should be formatted using Ruff before
   being merged into `main`. An easy way to do this is configure your editor
   to enable "Format on Save". 

### DAQ PC Installation

Limewire is installed on the DAQ PC using `uv` because it installs
Limewire in a virtual environment while globally exposing the `limewire`
command-line entry point. To download the latest version from GitHub, use
the following command.

```
uv tool upgrade limewire
```

## How to Run Limewire

Although Limewire is meant to run on the DAQ PC connected to the flight
computer via Ethernet, there are three alternate configurations you can use
that make it easier to test Limewire since the flight computer TCP firmware
has yet to be written (as of Jan 15, 2024). In order from easiest/least
realistic to hardest/most realistic, they are:

1. Limewire, Synnax, and FC Simulator running on your development machine
2. Limewire and Synnax running on the DAQ PC, FC Simulator running on your
   development machine, connected via WiFi
3. Limewire and Synnax running on the DAQ PC, FC Simulator running on your
   development machine, connected via Ethernet
4. Limewire and Synnax running on the DAQ PC, flight computer connected via
   Ethernet

### Running the FC Simulator

To run the FC Simulator, you'll need to know how you're connecting to
Limewire.

If you're using local Limewire and Synnax (Configuration 1), then your IP
address will be `localhost`.

If you're connecting to the DAQ PC via WiFi (Configuration 2):

1. Make sure you're connected to the University of Michigan WiFi. If you
   aren't on campus, you can use the 
   [UMVPN](https://its.umich.edu/enterprise/wifi-networks/vpn/getting-started)
   service. If you need help getting this set up properly, contact Rohan
   Satapathy on Slack.
   
2. Find your public IP address. The method to do this varies based on your
   operating system, but you should end up with a IPv4 address that looks
   like `35.X.X.X`. On macOS, the command to do this is `ipconfig getifaddr
   en0`.

If you're connecting to the DAQ PC via Ethernet (Configuration 3):

1. Log into the DAQ PC, go to network settings, and find the Ethernet IP
   address and subnet mask.

2. Find your development machine's network settings and ensure that the
   subnet mask matches and that the your computer's IP address is valid for
   that subnet mask. 

   On macOS, this can be done by going to Settings > Network > Ethernet >
   Details > TCP/IP, set "Configure IPv4" to "Manually", then change the IP
   address and subnet mask. 

   A simple strategy for making sure the IP address is valid is to take the
   IP address of the DAQ PC and incrementing the last octet by 1. Since
   there are only two devices in the network, this guarantees that there are
   no IP address conflicts.

Once you've determined your development machine's IP address, open a new
terminal window and start the FC Simulator. Configure the number of seconds
that the simulator sends telemetry messages for each client connection by
setting the `runtime` argument.

```shell
uv run python -m fc_simulator [ip-address]:8888 [runtime]
```

You might receive a pop-up asking if you want to allow Python to accept
incoming network connections. Make sure this option is enabled.

### Running Limewire

If you're running Limewire on the DAQ PC:

1. Use `ssh` to access the DAQ PC. Then, switch to PowerShell (it's just
   better, fight me 😤)

   ```shell
   ssh [username]@[daq-pc-ip-address]
   powershell
   ```
   To get the username and IP address of the DAQ PC, contact Rohan Satapathy
   on Slack.

2. Install the latest version of Limewire on the DAQ PC.

   ```shell
   uv tool upgrade limewire
   ```

3. Set the environment variables needed to run Limewire. These are contained
   in a file called `limewire_env.ps1` in the DAQ PC's home directory. If
   you haven't already, make sure you're in PowerShell by typing
   `powershell` at the command prompt.

   ```pwsh-console
   .\limewire_env.ps1
   ```
   

4. Run Limewire.
   
   ```shell
   limewire [ip-address]:8888
   ```

If you're running Limewire on your local machine:

1. Open a new terminal window and start your local Synnax cluster using
   [these
   instructions](https://docs.synnaxlabs.com/reference/cluster/quick-start?platform=macos).
   I recommend using the Docker container method, but feel free to use any
   method that works well on your system.

2. Open another terminal window and set the environment variables needed to
   authenticate with Synnax. 

   On macOS/Linux:
   ```shell
   export SYNNAX_HOST="localhost"
   export SYNNAX_PORT="9090"
   export SYNNAX_USERNAME="<insert-synnax-username-here>"
   export SYNNAX_PASSWORD="<insert-synnax-password-here>"
   # If SYNNAX_SECURE should be on:
   export SYNNAX_SECURE=1
   export LIMEWIRE_DEV_SYNNAX=1
   ```

   On Windows (make sure you're using PowerShell):
   ```pwsh-console
   $Env:SYNNAX_HOST="localhost"
   $Env:SYNNAX_PORT="9090"
   $Env:SYNNAX_USERNAME="<insert-synnax-username-here>"
   $Env:SYNNAX_PASSWORD="<insert-synnax-password-here>"
   # If SYNNAX_SECURE should be on:
   $Env:SYNNAX_SECURE="1"
   $Env:LIMEWIRE_DEV_SYNNAX="1"
   ```

   NOTE: Synnax has a limit of 50 channels without getting a license key,
   so the `LIMEWIRE_DEV_SYNNAX` only creates channels associated with the
   flight computer to avoid hitting that limit in order to enable local
   testing.

3. Run Limewire.

   ```shell
   uv run python -m limewire localhost:8888
   ```

## Project Structure

This repository currently contains three packages in the `src` directory:

- `limewire`: The Limewire driver, a TCP client that runs on the DAQ
  PC and processes telemetry data from the flight computer.
- `fc_simulator`: The Flight Computer Simulator, a TCP server that acts
  as a stand-in for the Flight Computer while its Ethernet issues are being
  debugged, enabling testing of Limewire.

