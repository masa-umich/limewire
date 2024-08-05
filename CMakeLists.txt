cmake_minimum_required(VERSION 3.10)
project(SimpleOPCUAServer)

set(CMAKE_CXX_STANDARD 11)

# Include open62541
include_directories(/home/jack/Projects/MASA/limewire/limewire-opc-ua/open62541)

# Add executable
add_executable(simple_opcua_server main.cpp)

# Link open62541
target_link_libraries(simple_opcua_server /home/jack/Projects/MASA/limewire/limewire-opc-ua/open62541/build/bin/open62541)