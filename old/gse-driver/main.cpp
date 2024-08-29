#include "reader.h"
#include "writer.h"
#include "gse-driver/daq/mock.h"
#include <iostream>
#include <csignal>

/// @brief Client config.
auto client_cfg = synnax::Config{
    .host = "synnax.masa.engin.umich.edu",
    .port = 80,
    .username = "synnax",
    .password = "seldon",
    .ca_cert_file = "/usr/local/synnax/certs/ca.crt"};

/// @brief Calibration writer config.
auto calibration_writer_cfg = synnax::WriterConfig{
    // Note: calibration_keys needs to be set in main.
    .start = synnax::TimeStamp::now(),
    .authorities = std::vector<synnax::Authority>{synnax::ABSOLUTE},
    .subject = synnax::Subject{.name = "calibration_writer"}};

auto ack_writer_cfg = synnax::WriterConfig{
    // Note: ack keys needs to be set in main.
    .start = synnax::TimeStamp::now(),
    .authorities = std::vector<synnax::Authority>{synnax::ABSOLUTE},
    .subject = synnax::Subject{.name = "ack_writer"}};

void signalHandler(int signum)
{
#if DEBUG
    std::cout << "Shutting down..." << std::endl;
#endif

    Reader::stop();
    Command::stop();

#if DEBUG
    std::cout << "Driver shut down gracefully." << std::endl;
#endif
}

int main()
{
    // Register signal handler for Ctrl+C
    signal(SIGINT, signalHandler);

    /* READER SETUP */

#if DEBUG
    std::cout << "Attempting to connect to synnax..." << std::endl;
#endif

    // Create reader client.
    auto reader_client = std::make_unique<synnax::Synnax>(client_cfg);

#if DEBUG
    std::cout << "Success." << std::endl;
#endif

    // Set up ai_keys vector, which will be passed into the writer.
    std::vector<synnax::ChannelKey> ai_keys;
    ai_keys.reserve(N_CHANS + 1);

#if DEBUG
    std::cout << "Retrieving gse_time..." << std::endl;
#endif

    // Retrieve index channel for calibrations.
    auto [calibration_index_channel, err1] = reader_client->channels.retrieve("gse_ai_time");
    if (!err1.ok())
    {
#if DEBUG
        std::cerr << err1.what() << std::endl;
        std::cerr << "Note: Synnax server may be down." << std::endl;
#endif
        while (!err1.ok())
        {
#if DEBUG
            std::cerr << "Retrying..." << std::endl;
#endif
            std::this_thread::sleep_for(std::chrono::seconds(5));
            auto [calibration_index_channel, err1] = reader_client->channels.retrieve("gse_ai_time");
        }
    }

#if DEBUG
    std::cout << "Success." << std::endl;
#endif

    // Push back index key into ai_keys.
    ai_keys.emplace_back(calibration_index_channel.key);

    // Retrieve calibration channels.
    std::vector<std::string> ai_names;
    ai_names.reserve(N_CHANS);
    for (size_t i = 1; i <= N_CHANS; i++)
        ai_names.emplace_back("gse_ai_" + std::to_string(i));
#if DEBUG
    std::cout << "Attempting retrieve calibration channels..." << std::endl;
#endif

    auto [calibration_channels, err2] = reader_client->channels.retrieve(ai_names);
    if (!err2.ok())
    {
#if DEBUG
        std::cerr << err2.message() << std::endl;
#endif
        return -1; // TODO: Change return.
    }

#if DEBUG
    std::cout << "Success." << std::endl;
#endif

    // Push back value ai_keys.
    for (size_t i = 0; i < N_CHANS; i++)
        ai_keys.emplace_back(calibration_channels[i].key);

    // Create DAQ reader.
    std::unique_ptr<DAQ::Reader> daq_reader = std::make_unique<DAQ::Reader>();

    // Set ai_keys to writer.
    calibration_writer_cfg.channels = ai_keys;

#if DEBUG
    std::cout << "Initializing reader..." << std::endl;
#endif

    // Initialize the reader.
    Reader::init(std::move(reader_client), std::move(daq_reader), std::move(calibration_writer_cfg));

#if DEBUG
    std::cout << "Success." << std::endl;
#endif

    /* WRITER SETUP */

    // Create writer config.
    auto writer_client = std::make_unique<synnax::Synnax>(client_cfg);

    // Ack keys.
    std::vector<synnax::ChannelKey> ack_keys;
    ack_keys.reserve(1 + N_VALVES);

#if DEBUG
    std::cout << "Retrieving ack index channel..." << std::endl;
#endif

    // Retrieve index channel for calibrations.
    auto [ack_channel_index, err3] = writer_client->channels.retrieve("gse_doa_time");
    if (!err3.ok())
    {
#if DEBUG
        std::cerr << err3.message() << std::endl;
#endif
        return -1; // TODO: Change return.
    }

#if DEBUG
    std::cout << "Success." << std::endl;
#endif

    // Push back index into ack keys.
    ack_keys.emplace_back(ack_channel_index.key);

    // Retrieve ack channels.
    std::vector<std::string> ack_names;
    ai_names.reserve(N_VALVES);
    for (size_t i = 1; i <= N_VALVES; i++)
        ack_names.emplace_back("gse_doa_" + std::to_string(i));

#if DEBUG
    std::cout << "Retrieving ack channels..." << std::endl;
#endif

    auto [ack_channels, err4] = writer_client->channels.retrieve(ack_names);
    if (!err4.ok())
    {
#if DEBUG
        std::cerr << err4.message() << std::endl;
#endif
        return -1; // TODO: Change return.
    }

#if DEBUG
    std::cout << "Success." << std::endl;
#endif

    // Push back into ack keys.
    for (size_t i = 0; i < N_VALVES; i++)
        ack_keys.emplace_back(ack_channels[i].key);

    // Set ack writer config keys.
    ack_writer_cfg.channels = ack_keys;

    // Create DAQ writer.
    std::unique_ptr<DAQ::Writer> daq_writer = std::make_unique<DAQ::Writer>();

#if DEBUG
    std::cout << "Initializing writer..." << std::endl;
#endif

    // Initialize the writer.
    Command::init(std::move(writer_client), std::move(daq_writer), ack_writer_cfg);

#if DEBUG
    std::cout << "Success." << std::endl;
    std::cout << "Starting data, calibration threads..." << std::endl;
#endif

    // Start reader threads.
    auto [data_thread, calibration_thread] = Reader::start();

#if DEBUG
    std::cout << "Success." << std::endl;
    std::cout << "Starting command thread..." << std::endl;
#endif

    // Start writer threads.
    auto command_thread = Command::start();

#if DEBUG
    std::cout << "Success." << std::endl;
#endif

    data_thread.join();
    calibration_thread.join();
    command_thread.join();

    return 0;
}
