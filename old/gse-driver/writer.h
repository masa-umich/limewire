#pragma once

#include "synnax/synnax.h"
#include "daq/writer.h"
#include <string>
#include <utility>
#include <thread>
#include <shared_mutex>

class Command
{
public:
    static freighter::Error init(std::unique_ptr<synnax::Synnax> client_, std::unique_ptr<DAQ::Writer> writer_, synnax::WriterConfig writer_cfg);

    /// @brief Starts the command thread. Returns the started thread.
    static std::thread start();

    /// @brief Stops the command thread. Returns nothing.
    static void stop();

private:
    /// @brief Handles the main logic.
    static freighter::Error run();

    /// @brief Thread to commit writer.
    static void commitWriter();

    /// @brief Client used to open control channels.
    static std::unique_ptr<synnax::Synnax> client;

    /// @brief To handle for stopping while blocked.
    static synnax::Streamer *streamer;

    /// @brief The digital writer to the daq.
    static std::unique_ptr<DAQ::Writer> daq;

    /// @brief Mutex for running.
    static std::shared_mutex running_mut;

    /// @brief Mutex for writer.
    static std::mutex writer_mut;

    /// @brief Used to see if we are still running.
    static bool running;

    /// @brief The writer back to synnax.
    static std::unique_ptr<synnax::Writer> writer;

    /// @brief Mutex for acked.
    static std::shared_mutex acked_mut;

    /// @brief Used to check if we have sent an ack recently.
    static bool acked;
};