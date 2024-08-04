#pragma once

#include "synnax/synnax.h"
#include "gse-driver/calibration/calibration.h"
#include "gse-driver/daq/reader.h"
#include "gse-driver/daq/writer.h"
#include "gse-driver/daq/daq_mappings.h"
#include <mutex>
#include <thread>
#include <memory>
#include <thread>
#include <shared_mutex>

struct CalibratedChannel
{
    synnax::Channel channel;
    std::shared_ptr<Calibration::Calibrator> calibration;
};

/// @brief This class is not intended to be instantiated; rather, it is a purely static
/// class.
class Reader
{
public:
    /// @brief Must be called before call to run.
    /// @return whether or not init was successful.
    static freighter::Error init(std::unique_ptr<synnax::Synnax> client_, std::unique_ptr<DAQ::Reader> reader_, synnax::WriterConfig writer_cfg);

    static std::pair<std::thread, std::thread> start();

    static void stop();

    // For gtest.
    friend class TestReader_TestBasic_Test;

private:
    static void run();

    static freighter::Error listenForUpdates();

    static freighter::Error processUpdate();

    /// Mutex for running.
    static std::shared_mutex running_mut;

    /// Mutex for channels.
    static std::shared_mutex channels_mut;

    /// Client and writer.
    static std::unique_ptr<synnax::Synnax> client;
    static std::unique_ptr<synnax::Writer> writer;
    static std::unique_ptr<DAQ::Reader> reader;

    /// To handle for stopping while blocked.
    static synnax::Streamer *updates;

    /// Calibration channels.
    static std::vector<CalibratedChannel> channels;
    /// Config for writer.
    static synnax::WriterConfig writer_config;

    /// Analog data.
    static std::shared_ptr<Matrix<float>> data;
    static std::shared_ptr<std::vector<int64_t>> time;

    /// Whether or not threads are still running.
    static bool running;
};
