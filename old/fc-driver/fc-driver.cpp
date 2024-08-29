/* 
*  Flight Computer to Synnax Driver
*  Purpose: Interface the TCP reader and writer with the synnax reader and writer
*  Author: Jackmh
*  Date: March 22, 2024
*/ 

/* Outline:
*  Make a class that will handle the flight computer connection
*  It will automatically handle the connection and disconnection along with the mutex locks needed
*  This class will be handed to the TCP reader & writer when we start their threads 
*  
*  Start the Synnax reader thread
*  Start the Synnax writer thread
*  If synnax connection is OK then
*  Start the TCP reader thread
*  Start the TCP writer thread
*  If TCP connection is OK then
*  Start translating data from the TCP reader to the Synnax writer
*  Start translating data from the Synnax reader to the TCP writer
*/ 
#include "synnax/reader.h"
#include "synnax/writer.h"
#include "tcp/tcpreader.h"
#include "tcp/tcpwriter.h"
#include <sys/socket.h>
#define FC_IP 192168050010;

class Connection {
    public:
        int Connection() {
            // Create a socket
            int socket;
            int port = 80;
            struct sockaddr_in server_address;

            socket_fd = socket(AF_INET, SOCK_STREAM, 0);
            if (socket_fd == -1) {
                // Handle socket creation error
                // You can throw an exception or return an error code
            
            }
        }

        int send() {
            // Send data over the connection
            return 0;
        }

        int receive() {
            // Receive data over the connection
            return 0;
        }

        int close() {
            // Close the connection
            close(socket_fd);
            return 0;
        }

    private:
        int socket_fd;
};


/// @brief Client config.
/// This is the API we will be using to connect to the synnax server.
auto client_cfg = synnax::Config{
    .host = "synnax.masa.engin.umich.edu",
    .port = 80,
    .username = "synnax",
    .password = "seldon",
    .ca_cert_file = "/usr/local/synnax/certs/ca.crt"
};

/// @brief Calibration writer config.
auto calibration_writer_cfg = synnax::WriterConfig {
    // Note: calibration_keys needs to be set in main.
    .start = synnax::TimeStamp::now(),
    .authorities = std::vector<synnax::Authority>{synnax::ABSOLUTE},
    .subject = synnax::Subject{.name = "calibration_writer"}
};

auto ack_writer_cfg = synnax::WriterConfig {
    // Note: ack keys needs to be set in main.
    .start = synnax::TimeStamp::now(),
    .authorities = std::vector<synnax::Authority>{synnax::ABSOLUTE},
    .subject = synnax::Subject{.name = "ack_writer"}
};

void signalHandler(int signum) {
    // Stop threads
    Reader::stop();
    Command::stop();
}

int main() {
    // Register signal handler for Ctrl+C
    signal(SIGINT, signalHandler);

    /* READER SETUP */
    // Create reader client.
    auto reader_client = std::make_unique<synnax::Synnax>(client_cfg);

    // Set up ai_keys vector, which will be passed into the writer.
    std::vector<synnax::ChannelKey> ai_keys;
    ai_keys.reserve(N_CHANS + 1);

    // Retrieve index channel for calibrations.
    auto [calibration_index_channel, err1] = reader_client->channels.retrieve("gse_ai_time");
    
    if (!err1.ok()) {
        while (!err1.ok()) {
            // Retrying every 5 seconds
            std::this_thread::sleep_for(std::chrono::seconds(5));
            auto [calibration_index_channel, err1] = reader_client->channels.retrieve("gse_ai_time");
        }
    }

    // Push back index key into ai_keys.
    ai_keys.emplace_back(calibration_index_channel.key);

    // Retrieve calibration channels.
    std::vector<std::string> ai_names;
    ai_names.reserve(N_CHANS);
    for (size_t i = 1; i <= N_CHANS; i++) {
        ai_names.emplace_back("gse_ai_" + std::to_string(i));
    }

    // Retrieve calibration channels.
    auto [calibration_channels, err2] = reader_client->channels.retrieve(ai_names);
    if (!err2.ok()) {
        return -1; // TODO: Change return.
    }

    // Success, push back values into ai_keys.
    // Push back value ai_keys.
    for (size_t i = 0; i < N_CHANS; i++) {
        ai_keys.emplace_back(calibration_channels[i].key);
    }
    // Create DAQ reader.
    std::unique_ptr<DAQ::Reader> daq_reader = std::make_unique<DAQ::Reader>();

    // Set ai_keys to writer.
    calibration_writer_cfg.channels = ai_keys;

    // Initialize the reader.
    Reader::init(std::move(reader_client), std::move(daq_reader), std::move(calibration_writer_cfg));

    /* WRITER SETUP */
    // Create writer config.
    auto writer_client = std::make_unique<synnax::Synnax>(client_cfg);

    // Ack keys.
    std::vector<synnax::ChannelKey> ack_keys;
    ack_keys.reserve(1 + N_VALVES);

    // Retrieve index channel for calibrations.
    auto [ack_channel_index, err3] = writer_client->channels.retrieve("gse_doa_time");
    if (!err3.ok()) {
        return -1; // TODO: Change return.
    }

    // Push back index into ack keys.
    ack_keys.emplace_back(ack_channel_index.key);

    // Retrieve ack channels.
    std::vector<std::string> ack_names;
    ai_names.reserve(N_VALVES);
    for (size_t i = 1; i <= N_VALVES; i++) {
        ack_names.emplace_back("gse_doa_" + std::to_string(i));
    }

    auto [ack_channels, err4] = writer_client->channels.retrieve(ack_names);
    if (!err4.ok()) {
        return -1; // TODO: Change return.
    }

    // Push back into ack keys.
    for (size_t i = 0; i < N_VALVES; i++) {
        ack_keys.emplace_back(ack_channels[i].key);
    }

    // Set ack writer config keys.
    ack_writer_cfg.channels = ack_keys;

    // Create DAQ writer.
    std::unique_ptr<DAQ::Writer> daq_writer = std::make_unique<DAQ::Writer>();

    // Initialize the writer.
    Command::init(std::move(writer_client), std::move(daq_writer), ack_writer_cfg);

    // Start reader threads.
    auto [data_thread, calibration_thread] = Reader::start();

    // Start writer threads.
    auto command_thread = Command::start();

    // Threads started :)
    data_thread.join();
    calibration_thread.join();
    command_thread.join();

    return 0;
}
