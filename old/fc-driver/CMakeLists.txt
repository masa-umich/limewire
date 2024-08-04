cmake_minimum_required(VERSION 3.15)

set(PROJECT_TITLE flight-computer-synnax-driver)        # Project name
set(CMAKE_CXX_STANDARD 17)                              # Specifiy the C++ standard version

project(${PROJECT_TITLE})

# CHANGE THIS TO THE PATH OF THE SYNNAX HEADER FILES
# For the DAQ PC change this to "~/Dev/synnaxlabs/synnax/"
set(SYNNAX_DIR "/mnt/s/Projects/MASA/synnax/synnax/")
# CHANGE THIS TO THE PATH OF YOUR GRPC INSTALL
# I have no idea what this is for the daq pc lol
set(GRPC_INSTALL_DIR "/mnt/s/Projects/MASA/gse-driver/fc-driver/build/grpc/")
# Note: gRPC is what Synnax uses to communicate with itself
# Basically, it's a way to send messages between different programs 
# which we need to use because the Synnax server is written in Go
# and this driver is written in C++

# Find gRPC installation
include(FetchContent)
FetchContent_Declare(
  gRPC
  GIT_REPOSITORY https://github.com/grpc/grpc
  GIT_TAG        v1.40.0  # or any specific release tag you want to use
  DOWNLOAD_DIR   ${CMAKE_BINARY_DIR}/gRPC_download  # Directory to store downloaded content
)
set(FETCHCONTENT_QUIET OFF)
set(FETCHCONTENT_UPDATES_DISCONNECTED TRUE)  # Cache downloaded content
FetchContent_MakeAvailable(gRPC)

# These are relative to the Synnax directory so you shouldn't need to modify these
set(SYNNAX_CLIENT_DIR "${SYNNAX_DIR}/client/cpp/")
set(SYNNAX_FREIGHTER "${SYNNAX_DIR}/freighter/cpp/")
set(SYNNAX_FERRORS_PROTOS "${SYNNAX_DIR}/freighter/go/")
set(SYNNAX_TELEM_PROTOS "${SYNNAX_DIR}/x/go/telem/")
set(SYNNAX_API_PROTOS "${SYNNAX_DIR}/synnax/pkg/api/grpc/")

# Include the Synnax header directory
include_directories(${SYNNAX_CLIENT_DIR})
include_directories(${SYNNAX_FREIGHTER})
include_directories(${SYNNAX_FERRORS_PROTOS})
include_directories(${SYNNAX_TELEM_PROTOS})
include_directories(${SYNNAX_API_PROTOS})

# Add main.cpp file of the project root directory as a source file
set(SOURCE_FILES fc-driver.cpp)

# Include generated *.pb.h files
include_directories(${CMAKE_CURRENT_BINARY_DIR})

# Find all proto files recursively
file(GLOB_RECURSE PROTO_FILES ${CMAKE_CURRENT_SOURCE_DIR}/*.proto)

# Generate protobuf and gRPC sources dynamically
foreach(PROTO_FILE ${PROTO_FILES})
    get_filename_component(PROTO_DIR ${PROTO_FILE} DIRECTORY)
    get_filename_component(PROTO_NAME ${PROTO_FILE} NAME_WE)

    set(PROTO_SRC "${CMAKE_CURRENT_BINARY_DIR}/${PROTO_NAME}.pb.cc")
    set(PROTO_HDR "${CMAKE_CURRENT_BINARY_DIR}/${PROTO_NAME}.pb.h")
    set(GRPC_SRC "${CMAKE_CURRENT_BINARY_DIR}/${PROTO_NAME}.grpc.pb.cc")
    set(GRPC_HDR "${CMAKE_CURRENT_BINARY_DIR}/${PROTO_NAME}.grpc.pb.h")

    add_custom_command(
        OUTPUT ${PROTO_SRC} ${PROTO_HDR} ${GRPC_SRC} ${GRPC_HDR}
        COMMAND protoc
        ARGS --grpc_out "${CMAKE_CURRENT_BINARY_DIR}"
             --cpp_out "${CMAKE_CURRENT_BINARY_DIR}"
             -I "${PROTO_DIR}"
             --plugin=protoc-gen-grpc="${_grpc_cpp_plugin_executable}"
             "${PROTO_FILE}"
        DEPENDS ${PROTO_FILE}
        COMMENT "Generating C++ sources from ${PROTO_FILE}"
        VERBATIM
        PRE_BUILD
    )

    list(APPEND GENERATED_FILES ${PROTO_SRC} ${PROTO_HDR} ${GRPC_SRC} ${GRPC_HDR})
endforeach()

# Create the executable
add_executable(${PROJECT_TITLE} ${SOURCE_FILES} ${GENERATED_FILES})
target_link_libraries(${PROJECT_TITLE} grpc++)

# Include the Synnax header directory for the target
target_include_directories(${PROJECT_TITLE} PUBLIC ${SYNNAX_CLIENT_DIR})
target_include_directories(${PROJECT_TITLE} PUBLIC ${SYNNAX_FREIGHTER})
target_include_directories(${PROJECT_TITLE} PUBLIC ${SYNNAX_FERRORS_PROTOS})
target_include_directories(${PROJECT_TITLE} PUBLIC ${SYNNAX_TELEM_PROTOS})
target_include_directories(${PROJECT_TITLE} PUBLIC ${SYNNAX_API_PROTOS})