This is still a work in progress and doesn't even compile atm
1. install synnax
2. modify the CMakeLists.txt file to have the correct path to your synnax install
3. install [gRPC](https://grpc.io/docs/languages/cpp/quickstart/)
4. modify the CMakeLists.txt file to include your gRPC install

to run this use the cmake file:
```bash
cd fc-driver/build
cmake --build .
```
or run the build.sh script if you're lazy
```bash
bash fc-driver/build.sh
```