/// GTest.
#include <gtest/gtest.h>

/// Internal
#include "gse-driver/writer.h"
#include "gse-driver/daq/mock.h"

TEST(testWriter, testWriterBasic)
{
    // Setup client config.
    auto client_cfg = synnax::Config{
        .host = "localhost",
        .port = 9091,
        .username = "synnax",
        .password = "seldon",
    };

    // Create client.
    auto client = std::make_unique<synnax::Synnax>(client_cfg);

    // Set up doc_keys and doa_vectors, used to construct control and ack channels..
    std::vector<synnax::ChannelKey> doc_keys;
    std::vector<synnax::ChannelKey> doa_keys;
    doc_keys.reserve(2 * N_VALVES);
    doa_keys.reserve(1 + N_VALVES);

    // Create 24 channels for each valve.
    std::vector<synnax::Channel> doc_channel_values;
    std::vector<synnax::Channel> doc_channel_indexes;
    std::vector<synnax::Channel> doa_channels;
    doc_channel_values.resize(N_VALVES);
    doc_channel_indexes.resize(N_VALVES);
    doa_channels.resize(N_VALVES);

    // First, initialize the time channels.
    for (size_t i = 1; i <= N_VALVES; i++)
    {
        // Create the index channel i for controls.
        doc_channel_indexes[i] = synnax::Channel{
            "gse_doc_time_" + std::to_string(i),
            synnax::TIMESTAMP,
            0,
            true};
    }

    // Create index for ack channels.
    auto doa_channel_index = synnax::Channel{
        "gse_doa_time",
        synnax::TIMESTAMP,
        0,
        true};

    std::cout << "Creating index channels..." << std::endl;

    // First create control index channels.
    auto err_create_doc_channel_indexes = client->channels.create(doc_channel_indexes);
    // Create ack index channel.
    auto err_create_doa_channel_index = client->channels.create(doa_channel_index);

    // Wait a moment for database to open.
    std::this_thread::sleep_for(std::chrono::milliseconds(10));

    ASSERT_TRUE(err_create_doc_channel_indexes.ok());
    ASSERT_TRUE(err_create_doa_channel_index.ok());

    std::cout << "Success." << std::endl;
    std::cout << "Creating value channels..." << std::endl;

    // Then, create value channels.
    for (size_t i = 1; i <= N_VALVES; i++)
    {
        // Create control channel for valve i.
        doc_channel_values[i] = synnax::Channel{
            "gse_doc_" + std::to_string(i),
            synnax::UINT8,
            doc_channel_indexes[i].key,
            false};

        // Create the ack channel i.
        doa_channels[i] = synnax::Channel{
            "gse_doa_" + std::to_string(i),
            synnax::UINT8,
            doa_channel_index.key,
            false};
    }

    // Then, create control value channels.
    auto err_create_doc_channel_values = client->channels.create(doc_channel_values);
    // Finally, create ack value channels.
    auto err_create_doa_channel_values = client->channels.create(doa_channels);

    ASSERT_TRUE(err_create_doa_channel_values.ok());
    ASSERT_TRUE(err_create_doc_channel_values.ok());

    std::cout << "Success." << std::endl;

    doa_keys.emplace_back(doa_channel_index.key);

    // Push all keys of all channels into keys vectors.
    for (size_t i = 0; i < N_VALVES; i++)
    {
        doc_keys.emplace_back(doc_channel_indexes[i].key);
        doa_keys.emplace_back(doa_channels[i].key);
    }
    for (size_t i = 0; i < N_VALVES; i++)
        doc_keys.emplace_back(doc_channel_values[i].key);

    // Initialize a writer to write to
    // control channel.
    auto now = synnax::TimeStamp::now();
    auto [control_writer, wErr] = client->telem.openWriter(synnax::WriterConfig{
        .channels = doc_keys,
        .start = now,
        .authorities = std::vector<synnax::Authority>{synnax::ABSOLUTE, synnax::ABSOLUTE},
        .subject = synnax::Subject{.name = "test_control_writer"},
    });
    ASSERT_TRUE(wErr.ok()) << wErr.message();

    // Ensure database updates.
    std::this_thread::sleep_for(std::chrono::milliseconds(10));

    // Create a reader to check for ack updates.
    auto [ack_listener, err2] = client->telem.openStreamer(synnax::StreamerConfig{
        .channels = doa_keys,
        .start = now,
    });
    ASSERT_TRUE(err2.ok()) << err2.message();

    // Create the ack writer.
    auto writer_cfg = synnax::WriterConfig{
        .channels = doa_keys,
        .start = now,
        .authorities = std::vector<synnax::Authority>{synnax::ABSOLUTE},
        .subject = synnax::Subject{.name = "test_ack_writer"}};

    // Create a mock writer.
    std::unique_ptr<DAQ::Writer> mock_writer = std::make_unique<DAQ::mockWriter>();

    // Hold onto for later use.
    DAQ::mockWriter *mock_writer_ptr = static_cast<DAQ::mockWriter *>(mock_writer.get());

    std::cout << "Initialize command thread..." << std::endl;

    // Initialize the writer
    Command::init(std::move(client), std::move(mock_writer), writer_cfg);

    std::cout << "Starting command thread..." << std::endl;

    // Create the command thread.
    auto command_thread = Command::start();

    std::cout << "Started." << std::endl;

    // Ensure database updates.
    std::this_thread::sleep_for(std::chrono::milliseconds(50));

    // Write to controls.
    auto frame = synnax::Frame(4);

    frame.add(
        doc_channel_indexes[5].key,
        synnax::Series(std::vector<int64_t>{(now + synnax::SECOND).value}));

    frame.add(
        doc_channel_values[5].key,
        synnax::Series(std::vector<uint8_t>{(uint8_t)1}));

    frame.add(
        doc_channel_indexes[15].key,
        synnax::Series(std::vector<int64_t>{(now + synnax::SECOND).value}));

    frame.add(
        doc_channel_values[15].key,
        synnax::Series(std::vector<uint8_t>{(uint8_t)1}));

    std::cout << "Sending frame..." << std::endl;

    // Write to controls.
    ASSERT_TRUE(control_writer.write(std::move(frame)));

    std::cout << "Sent." << std::endl;

    // Ensure database updates.
    std::this_thread::sleep_for(std::chrono::milliseconds(30));

    std::cout << "Reading response from ack." << std::endl;
    // Ensure we receive an ack message.
    auto [frame_, err3] = ack_listener.read();

    std::cout << "Received response from ack." << std::endl;

    ASSERT_TRUE(err3.ok());

    // Now, we can close the writer.
    Command::stop();
    command_thread.join();

    // Ensure that the mock writer has all valves set to closed.
    ASSERT_EQ(mock_writer_ptr->valves, 0);

    ASSERT_EQ(frame_.series->size(), N_VALVES + 1);
    for (size_t i = 1; i < N_VALVES + 1; i++)
    {
        if (i - 1 == 5 || i - 1 == 15)
            ASSERT_EQ(frame_.series->at(i).uint8()[0], (uint8_t)1);
        else
            ASSERT_EQ(frame_.series->at(i).uint8()[0], (uint8_t)0);
    }
}