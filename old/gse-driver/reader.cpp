/// Local.
#include "gse-driver/reader.h"

// std
#include <regex>

std::shared_mutex Reader::running_mut;
std::shared_mutex Reader::channels_mut;
std::unique_ptr<synnax::Synnax> Reader::client;
std::unique_ptr<synnax::Writer> Reader::writer;
std::unique_ptr<DAQ::Reader> Reader::reader;
std::vector<CalibratedChannel> Reader::channels;
synnax::WriterConfig Reader::writer_config;
std::shared_ptr<Matrix<float>> Reader::data;
std::shared_ptr<std::vector<int64_t>> Reader::time;
synnax::Streamer *Reader::updates;
bool Reader::running = false;

freighter::Error Reader::init(std::unique_ptr<synnax::Synnax> client_, std::unique_ptr<DAQ::Reader> reader_, synnax::WriterConfig writer_cfg)
{
    client = std::move(client_);
    reader = std::move(reader_);
    writer_config = std::move(writer_cfg);

    auto [writer_, err] = client->telem.openWriter(writer_config);

    if (!err.ok())
    {
        std::cerr << err.message() << std::endl;
        return err;
    }

    channels.resize(N_CHANS);

    writer = std::make_unique<synnax::Writer>(std::move(writer_));

    return freighter::TYPE_NIL;
}

std::pair<std::thread, std::thread> Reader::start()
{
    running = true;

    // First, make call to processUpdate to initialize channels.
    processUpdate();

    // Create a thread to run calibration thread.
    std::thread calibration_thread(listenForUpdates);

    // Create a thread to run data thread
    std::thread data_thread(run);

    return {std::move(data_thread), std::move(calibration_thread)};
}

void Reader::stop()
{
    std::cerr << "sent closeSend" << std::endl;
    updates->closeSend();
    reader->stop();

    std::unique_lock<std::shared_mutex> running_lock{running_mut};
    running = false;
    running_lock.unlock();
}

void Reader::run()
{
    /// @brief Matrix of size N_CHANS, ANALOG_N
    data = std::make_shared<Matrix<float>>(N_CHANS, ANALOG_N);
    time = std::make_shared<std::vector<int64_t>>(ANALOG_N);

    reader->start();

    // For committing non-frequently.
    int curr_commit_iters = 0;
    constexpr int MAX_COMMIT_ITERS = ((30 * 200) / ANALOG_N);

    std::shared_lock<std::shared_mutex> running_lock{running_mut};
    do
    {
        running_lock.unlock();
        reader->readAnalog(data, time);

        auto f = synnax::Frame(N_CHANS);

        // Need to push back index channel (time) first.
        f.add(writer_config.channels.front(), synnax::Series{*time});

        // Iterate through the channels by index, and apply the calibration.
        for (size_t j = 0; j < channels.size(); j++)
        {
            std::shared_lock<std::shared_mutex> channels_lock{channels_mut};
            auto ch = channels[j];
            channels_lock.unlock();

            // Slice the data for this channel.
            auto start = j * ANALOG_N;
            auto end = start + ANALOG_N;

            // Apply the calibration.
            ch.calibration->transform(data->vec(), size_t(start), size_t(end));

            // Get slice after so that we can see calibration in tests.
            auto slice = std::vector<float>(data->vec().begin() + size_t(start), data->vec().begin() + size_t(end));

            f.add(ch.channel.key, synnax::Series{slice});
        }

        // Write to the framer.
        writer->write(std::move(f));
        if (curr_commit_iters == MAX_COMMIT_ITERS)
        {
            std::cerr << "Committing data thread..." << std::endl;
            auto [_, ok] = writer->commit();
            if (!ok)
            {
                // TODO: Add exception handling.
                std::cerr << "Unable to send frame to synnax from Reader::run()" << std::endl;
                return;
            }
            else
                std::cerr << "Successful commit." << std::endl;

            curr_commit_iters = 0;
        }

        curr_commit_iters++;
        running_lock.lock();
    } while (running);
    running_lock.unlock();
}

freighter::Error Reader::listenForUpdates()
{
    auto [trigger, err1] = client->channels.retrieve("sy_active_range_set");

    if (!err1.ok())
    {
        std::cerr << err1.message() << std::endl;
        return err1;
    }
    auto [updates_, err2] = client->telem.openStreamer(synnax::StreamerConfig{
        std::vector<synnax::ChannelKey>{trigger.key},
        synnax::TimeStamp::now()});

    updates = &updates_;

    if (!err2.ok())
    {
        std::cerr << err2.message() << std::endl;
        return err2;
    }

    std::shared_lock<std::shared_mutex> running_lock{running_mut};
    while (running)
    {
        running_lock.unlock();
        auto [_, err3] = updates_.read();

        std::cerr << "Calibrations thread: Received update. Updating..." << std::endl;

        // If we receive EOF then we have a graceful shutdown.
        if (err3.type == "freighter.eof")
        {
            return freighter::TYPE_NIL;
        }
        if (!err3.ok())
        {
            std::cerr << err3.message() << std::endl;
            return err3;
        }

        // Don't need the frame, only used to check for update.
        processUpdate();

        std::cerr << "Calibrations thread: Finished update." << std::endl;
        running_lock.lock();
    }
    running_lock.unlock();
    return freighter::TYPE_NIL;
}

freighter::Error Reader::processUpdate()
{
    auto [active_range, err0] = client->ranges.retrieveActive();

    // Data acquisition has stopped.
    if (!err0.ok())
    {
        std::unique_lock<std::shared_mutex> channels_lock{channels_mut};
        channels.clear();
        channels_lock.unlock();
        return err0;
    }

    /// TODO: Change to regex based search
    std::vector<std::string> names;
    names.reserve(N_CHANS);
    for (size_t i = 1; i <= N_CHANS; i++)
        names.emplace_back("gse_ai_" + std::to_string(i));

    auto [raw_channels, err1] = client->channels.retrieve(names);

    if (!err1.ok())
    {
        std::cerr << "Unable to retrieve raw channels." << std::endl;
        return err1;
    }

    // Sort by name.
    std::sort(raw_channels.begin(), raw_channels.end(), [](auto &left, auto &right)
              { return left.key < right.key; });

    // Iterate through each channel
    for (size_t i = 0; i < N_CHANS; i++)
    {
        auto ch = raw_channels[i];

        auto type_field = ch.name + "_type";
        auto [type, err2] = active_range.kv.get(type_field);
        if (!err2.ok())
        {
            std::cerr << "Unable to retrieve type from active range." << std::endl;
            return err2;
        }

        if (type == "TC")
        {
            // Accessing shared data, so we lock and unlock.
            std::unique_lock<std::shared_mutex> channels_lock{channels_mut};
            channels[i] = std::move(CalibratedChannel{ch, std::make_shared<Calibration::TC>()});
            channels_lock.unlock();
        }
        else if (type == "PT")
        {
            auto [offset, err3] = active_range.kv.get(ch.name + "_pt_offset");
            auto [scale, err4] = active_range.kv.get(ch.name + "_pt_slope");
            if (offset.empty() || scale.empty() || !err3.ok() || !err4.ok())
            {
                std::cerr << "Missing calibration parameters for PT channel " << ch.name << std::endl;
                continue;
            }
            auto cal = std::make_shared<Calibration::PT>(std::stof(offset), std::stof(scale));
            // Accessing shared data, so we lock and unlock.
            std::unique_lock<std::shared_mutex> channels_lock{channels_mut};
            channels[i] = std::move(CalibratedChannel{ch, cal});
            channels_lock.unlock();
        }
        else
        {
            std::cerr << "Unknown calibration type " << type << " for channel " << ch.name << std::endl;
            std::unique_lock<std::shared_mutex> channels_lock{channels_mut};
            channels[i] = std::move(CalibratedChannel{ch, std::make_shared<Calibration::NOOP>()});
            channels_lock.unlock();
        }
    }

    return freighter::TYPE_NIL;
}