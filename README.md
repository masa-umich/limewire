# Limewire

This repository contains the ground support software for MASA's Limelight
mission. There are two main components:

- __Limewire__: A driver that enables communication of telemetry and valve
  commands between the rocket and our database, Synnax.

- __Hydrant__: A web-based GUI that enables remote command and control of
  the flight hardware.

> [!NOTE] Although the telemetry + valve driver is only one component of the
ground software, the repository is called "Limewire" because Hydrant was
developed at a later point in time. This leads to a couple (rather
unfortunate) conventions:
> 
> - This README will mostly refer to Limewire, but you can mentally replace
>   "Limewire" with "Limewire and Hydrant" most of the time.
> - When "installing Limewire," you're actually installing both Limewire and
>   Hydrant, so there's no need to install Hydrant separately.

__Project Lead__: Ryan Wei

## Installation

If you want to use Limewire on the DAQ PC, follow the first set
of instructions. If you want to contribute to Limewire, follow the second
set of instructions.

### DAQ PC Installation

Limewire is installed on the DAQ PC using `uv` because it installs
Limewire in a virtual environment while globally exposing the `limewire`
command-line entry point. 

Start by checking if Limewire is installed on the DAQ PC. 

```
limewire
```

If Limewire is already installed, you should see log messages start to
appear in the terminal. If you see a "command not found" error, install
Limewire using the following command.

```
uv tool install git+https://github.com/masa-umich/limewire.git
```

If Limewire is already installed and you'd like to upgrade to the latest
version, run the following command.

```
uv tool upgrade limewire
```

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
   uv pip install -e .
   ```

5. Install [Ruff](https://github.com/astral-sh/ruff), a linter and code
   formatter for Python projects. If you use VS Code, you can install the
   [VS Code Ruff Extension](https://marketplace.visualstudio.com/items?itemName=charliermarsh.ruff).

   All code submitted to this project should be formatted using Ruff before
   being merged into `main`. An easy way to do this is configure your editor
   to enable "Format on Save".

## Running Limewire and Hydrant

During operations, Limewire and Hydrant should be run on the DAQ PC while
connected to the real flight computer. Assuming Limewire is installed
following the instructions above, run the following command in the DAQ PC
terminal to run Limewire:

```shell
limewire
```

> [!IMPORTANT]
> If Synnax is not running when Limewire is started, it will crash right
> away. Make sure Synnax is running on the DAQ PC before starting Limewire.

To run Hydrant, use the following command:

```shell
hydrant
```

To see all the runtime options available, run either command with the `-h/--help`
flag.

### Running development code on the DAQ PC

If you're working on Limewire or Hydrant in a development branch, you can
uninstall the mainline version and install Limewire from your development
branch.

```shell
uv tool uninstall limewire
uv tool install git+https://github.com/masa-umich/limewire.git@your-branch-name
```
After pointing the Limewire installation to the development branch, if you
add new commits to your branch, you can easily upgrade Limewire using the
following: 
```shell
uv tool upgrade limewire
```

If you install a development version of Limewire, you MUST restore the 
mainline version of Limewire after you're done.

```shell
uv tool uninstall limewire
uv tool install git+https://github.com/masa-umich/limewire.git
```

### Using FC Simulator

To make development easier, this repository contains a flight computer
simulator, `fc_simulator`, that can be run locally for testing. There are
two typical configurations that are used when running FC Simulator.

1. Limewire, Synnax, and FC Simulator running on your local machine.
2. Limewire and Synnax running on the DAQ PC and FC Simulator running on
   your local machine.

To run the FC simulator, follow the Limewire development installation
instructions to install the simulator on your local machine. Then, open a
new terminal, and activate the virtual environment for your project:

```
# Linux/macOS (bash/zsh)
source .venv/bin/activate

# Windows (CMD)
.venv\Scripts\activate.bat

# Windows (PowerShell)
.venv\Scripts\Activate.ps1
```

Next, start FC Simulator using the following command. (Note: Using `0.0.0.0`
ensures that the FC simulator serves across all network interfaces.)

```
fc_simulator 0.0.0.0:8888
```

You might receive a pop-up asking if you want to allow Python to accept
incoming network connections. Make sure this option is enabled.

Finally, start Limewire and connect to FC Simulator.

```
limewire [ip-address]:8888
```

Some caveats:

- If running Limewire locally:
   - You'll need open a new terminal to run Limewire, make sure you
     re-activate the virtual environment in this terminal.
   - The IP address field should be `127.0.0.1`.

- If running Limewire on the DAQ PC: 
   - Your local machine should be connected to the DAQ PC via Ethernet. Make
     sure and that your local IP is configured to be in the same subnet as
     the DAQ PC (here's how to change your local IP on [macOS](https://support.apple.com/en-in/guide/mac-help/mh141292/26/mac/26)
     and [Windows](https://support.microsoft.com/en-us/windows/essential-network-settings-and-tasks-in-windows-f21a9bbc-c582-55cd-35e0-73431160a1b9)).
     Contact Ryan Wei or Felix Foreman-Braunschweig for the DAQ PC local IP
     address or if you run into any issues with this process.
   - The IP address field should be whatever IP address you configured your
     local machine to be.


## Project Structure

This repository currently contains four packages in the `src` directory:

- `limewire`: The code for Limewire, which interfaces with the flight
   computer via TCP for valve commands and UDP for telemetry. 
- `fc_simulator`: The Flight Computer Simulator, a TCP server that acts
  as a stand-in for the Flight Computer and enables local testing for
  Limewire.
- `lmp`: A shared library that implements message serializing and
   deserializing for the Limelight Messaging Protocol.
- `hydrant`: A web-based GUI that enables remote command and control of the
  rocket hardware.

