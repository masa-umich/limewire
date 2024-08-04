/// GTest.
#include <gtest/gtest.h>

/// Internal
#include "fc-driver/reader.h"
#include "fc-driver/daq/mock.h"

TEST(TestReader, TestBasic)
{
    // Setup client config.
    auto client_cfg = synnax::Config{
        .host = "localhost",
        .port = 9090,
        .username = "synnax",
        .password = "seldon"
    };

    // Create client.
    auto client = std::make_unique<synnax::Synnax>(client_cfg);

    // Set up keys vector, which will be passed into the writer.
    std::vector<synnax::ChannelKey> keys;
    keys.reserve(N_CHANS + 1);

    // Create the index channel for calibrations.
    auto index = synnax::Channel{
        "gse_time",
        synnax::TIMESTAMP,
        0,
        true};

    ASSERT_TRUE(client->channels.create(index).ok());

    // Push back the index key.
    keys.emplace_back(index.key);

    // Create 80 channels, each representing a different physical measurement.
    std::vector<synnax::Channel> channels;
    channels.reserve(N_CHANS);
    for (size_t i = 1; i <= N_CHANS; i++)
    {
        channels.emplace_back(synnax::Channel{
            "gse_ai_" + std::to_string(i),
            synnax::FLOAT32,
            index.key,
            false});
    }

    ASSERT_TRUE(client->channels.create(channels).ok());

    for (size_t i = 0; i < N_CHANS; i++)
        keys.emplace_back(channels[i].key);

    // Create the writer config, which will be passed on to the
    // reader in init.
    auto now = synnax::TimeStamp::now();
    auto writer_cfg = synnax::WriterConfig{
        .channels = std::move(keys),
        .start = now,
        .authorities = std::vector<synnax::Authority>{synnax::ABSOLUTE},
        .subject = synnax::Subject{.name = "test_writer"}};
    std::unique_ptr<DAQ::Reader> mock_reader = std::make_unique<DAQ::mockReader>();

    // Create active range in  synnax
    auto [range, err2] = client->ranges.create(
        "test",
        synnax::TimeRange(
            synnax::TimeStamp(10),
            synnax::TimeStamp(20)));

    ASSERT_TRUE(err2.ok());
    ASSERT_TRUE(client->ranges.setActive(range.key).ok());

    // Create calibrations settings in range.

    // Pressure transducers.
    // We will setscale to 2 and offset to -3,
    // so that we should theoretically get (1 - (-3)) / 2 = 2
    for (size_t i = 1; i <= 36; i++)
    {
        ASSERT_TRUE(range.kv.set("gse_ai_" + std::to_string(i) + "_type", "PT").ok());
        ASSERT_TRUE(range.kv.set("gse_ai_" + std::to_string(i) + "_pt_slope", "2").ok());
        ASSERT_TRUE(range.kv.set("gse_ai_" + std::to_string(i) + "_pt_offset", "-3").ok());
    }
    // Current, load cell.
    for (size_t i = 37; i <= 64; i++)
        ASSERT_TRUE(range.kv.set("gse_ai_" + std::to_string(i) + "_type", "NOOP").ok());
    // Thermocouples.
    for (size_t i = 65; i <= 80; i++)
        ASSERT_TRUE(range.kv.set("gse_ai_" + std::to_string(i) + "_type", "TC").ok());

    // Create synnax channel.
    auto gse_daq_trigger_time = synnax::Channel{
        "gse_daq_trigger_time",
        synnax::TIMESTAMP,
        0,
        true};
    ASSERT_TRUE(client->channels.create(gse_daq_trigger_time).ok());

    // Create associated data channel.
    auto gse_trigger_data = synnax::Channel{
        "gse_daq_trigger",
        synnax::UINT8,
        gse_daq_trigger_time.key,
        false};

    ASSERT_TRUE(client->channels.create(gse_trigger_data).ok());

    // create a writer
    now = synnax::TimeStamp::now();
    auto [trigger_writer, wErr] = client->telem.openWriter(synnax::WriterConfig{
        .channels = std::vector<synnax::ChannelKey>{gse_daq_trigger_time.key, gse_trigger_data.key},
        .start = now,
        .authorities = std::vector<synnax::Authority>{synnax::ABSOLUTE, synnax::ABSOLUTE},
        .subject = synnax::Subject{.name = "test_writer"},
    });
    ASSERT_TRUE(wErr.ok()) << wErr.message();

    // Ensure database updates.
    std::this_thread::sleep_for(std::chrono::milliseconds(5));

    // Initialize the reader.
    Reader::init(std::move(client), std::move(mock_reader), std::move(writer_cfg));

    // Create a thread for the reader.
    auto [data_thread, calibration_thread] = Reader::start();

    // Send an update to calibrations.
    for (size_t i = 1; i <= 10; i++)
    {
        ASSERT_TRUE(range.kv.set("gse_ai_" + std::to_string(i) + "_type", "PT").ok());
        ASSERT_TRUE(range.kv.set("gse_ai_" + std::to_string(i) + "_pt_slope", "0.5").ok());
        ASSERT_TRUE(range.kv.set("gse_ai_" + std::to_string(i) + "_pt_offset", "-3").ok());
    }

    // Ensure thread gets to blocking point.
    std::this_thread::sleep_for(std::chrono::milliseconds(5));

    std::cerr << "Done waiting. Sending frame..." << std::endl;
    // Then, we will trigger a write to the database, which should call to calibrations.
    auto frame = synnax::Frame(2);
    frame.add(
        gse_daq_trigger_time.key,
        synnax::Series(std::vector<int64_t>{(now + synnax::SECOND).value}));
    frame.add(
        gse_trigger_data.key,
        synnax::Series(std::vector<uint8_t>{1}));

    // Write and trigger daq.
    ASSERT_TRUE(trigger_writer.write(std::move(frame)));

    // We should in theory have seen a change in the
    // channels in synnax, i.e. they have been calibrated.
    // Ensure database updates.
    std::this_thread::sleep_for(std::chrono::milliseconds(30));

    Reader::stop();

    data_thread.join();
    calibration_thread.join();

    std::cerr << "Reading data channel" << std::endl;

    // Pressure transducers.
    for (size_t i = 0; i < 10; i++)
    {
        for (size_t j = 0; j < ANALOG_N; j++)
        {
            ASSERT_NEAR(Reader::data->at(i, j), 8, 0.001);
        }
    }
    for (size_t i = 10; i < 36; i++)
    {
        for (size_t j = 0; j < ANALOG_N; j++)
        {
            ASSERT_NEAR(Reader::data->at(i, j), 2, 0.001);
        }
    }
    // Current, load cell.
    for (size_t i = 36; i < 64; i++)
    {
        for (size_t j = 0; j < ANALOG_N; j++)
        {
            ASSERT_NEAR(Reader::data->at(i, j), 1, 0.001);
        }
    }
    // Thermocouples.
    for (size_t i = 64; i < 80; i++)
    {
        for (size_t j = 0; j < 25; j++)
        {
            ASSERT_NEAR(Reader::data->at(i, j), 25.203155517578125, 0.001);
        }
    }
}