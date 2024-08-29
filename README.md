# Limewire
A driver for communication to Limelight and our GSE systems.

*Documentation last updated:* **8/13/2024**\
*Primary author:* **Jackmh**

## Installation
Clone this repo\
`git clone https://github.com/masa-umich/limewire.git`

Install Bazel-5.3.0\
`sudo apt-get install Bazel-5.3.0`\
*NOTE: must be using Bazel 5.3.0 specifically, or use Bazelisk*

Build or run with Bazel\
`./build.sh`\
or\
`./run.sh`\
*these are premade scripts, you can also use normal Bazel commands if you'd like*

## Notes
This project was designed to only be developed and run on Linux as we will be using networking APIs that are not available on Windows. A port to Windows may be possible but is not planned, I reccomend using WSL2 if you are on Windows.

Bazel has a weird directory naming scheme that goes like this:
- Every file you want to build or include must have a BUILD file in its directory
- In that BUILD file you must specify a **name** for the target you want to build (NOT just the name of the file)
- To specify where a ***Bazel*** file is use `\\directory:target_in_directory` 
    - Where `\\` is the root of the project
    - `:` Means a target inside the directory
    - And the target is the name specified in the BUILD file (again, not the file name)

The Bazel WORKSPACE file specifies external/remote dependencies for the project. For Limewire, this is the Synnax C++ Client Libraries, including gRPC and Freighter.

Because of these dependencies, it may take several minutes to build the project initially, subsequent builds should be faster due to caching.

Intellisense may be broken before the first build due to the dependencies not being present.

I don't like the way Bazel puts the binary file of a build inside some random folder and symlinks it, so I the build script copies the binary to the root of the project. You can still build with Bazel normally if you want, but you will need to modify the `.bazelrc` file if you want to re-enable the symlinks.

If things get messed up, do a `bazel clean` and it might be fixed. It basically just clears the cache that Bazel uses.