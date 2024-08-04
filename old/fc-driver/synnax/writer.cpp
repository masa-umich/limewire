#include "writer.h"
std::unique_ptr<synnax::Synnax> Command::client;
std::unique_ptr<DAQ::Writer> Command::daq;
std::unique_ptr<synnax::Writer> Command::writer;
synnax::Streamer *Command::streamer;
std::shared_mutex Command::running_mut;
std::mutex Command::writer_mut;
bool Command::running = false;
bool Command::acked = false;
std::shared_mutex Command::acked_mut;

freighter::Error Command::init(std::unique_ptr<synnax::Synnax> client_, std::unique_ptr<DAQ::Writer> daq_, synnax::WriterConfig writer_cfg)
{
    client = std::move(client_);
    daq = std::move(daq_);

    auto [writer_, err] = client->telem.openWriter(writer_cfg);

    if (!err.ok())
    {
        std::cerr << err.message() << std::endl;
        return err;
    }

    writer = std::make_unique<synnax::Writer>(std::move(writer_));

    return freighter::TYPE_NIL;
}

std::thread Command::start()
{
    running = true;

    auto command_thread = std::thread(run);

    return std::move(command_thread);
}

void Command::stop()
{
    streamer->closeSend();

    std::unique_lock<std::shared_mutex> running_lock{running_mut};
    running = false;
    running_lock.unlock();


    std::unique_lock<std::mutex> writer_lock{writer_mut};
    // This closes all valves.
    uint32_t res;
    do
    {
        res = daq->writeDigital(0xFFFFFFFF, 0x0);
    } while (res != 0);

    return;
}

void Command::commitWriter()
{
    auto last_time_committed = synnax::TimeStamp::now();

    std::shared_lock<std::shared_mutex> running_lock{running_mut};
    while (running)
    {

        running_lock.unlock();
        std::shared_lock<std::shared_mutex> acked_lock{acked_mut};
        if (acked && synnax::TimeSpan((synnax::TimeStamp::now() - last_time_committed).value) > synnax::SECOND * 30)
        {
            acked_lock.unlock();
            std::unique_lock<std::shared_mutex> change_acked_lock{acked_mut};
            acked = false;
            change_acked_lock.unlock();
            auto [_, ok] = writer->commit();
            last_time_committed = synnax::TimeStamp::now();
            if (!ok)
            {
                std::cerr << "Error committing ack writer: " << writer->error() << std::endl;
            }
        }
        else
        {
            acked_lock.unlock();
            std::this_thread::sleep_for(std::chrono::seconds(30));
        }

        running_lock.lock();
    }
    running_lock.unlock();
}

freighter::Error Command::run()
{

    auto commit_thread = std::thread(commitWriter);

    std::vector<std::string> control_channels_vec;
    for (auto i = 1; i <= N_VALVES; i++)
        control_channels_vec.emplace_back("gse_doc_" + std::to_string(i));

    auto [channels, err1] = client->channels.retrieve(control_channels_vec);

    if (!err1.ok())
    {
        std::cerr << err1.message() << std::endl;
        return err1;
    }

    std::vector<synnax::ChannelKey> keys;
    keys.reserve(channels.size());
    for (auto &channel : channels)
        keys.push_back(channel.key);

    auto [streamer_, err2] = client->telem.openStreamer(synnax::StreamerConfig{
        keys,
        synnax::TimeStamp::now(),
    });

    if (!err2.ok())
    {
        std::cerr << err2.message() << std::endl;
        return err2;
    }

    // Get ack channels.
    std::vector<std::string> ack_keys;
    ack_keys.reserve(N_VALVES);
    for (auto i = 1; i <= N_VALVES; i++)
        ack_keys.emplace_back("gse_doa_" + std::to_string(i));

    auto [acks, err3] = client->channels.retrieve(ack_keys);
    if (!err3.ok())
    {
        std::cerr << err3.message() << std::endl;
        return err3;
    }

    std::sort(acks.begin(), acks.end(), [](auto &left, auto &right)
              { return left.key < right.key; });

    // Should also get the ack time key
    auto [ack_time, err4] = client->channels.retrieve("gse_doa_time");
    if (!err4.ok())
    {
        std::cerr << err4.message() << std::endl;
        return err4;
    }

    // Make sure that streamer is able to be shut off.
    streamer = &streamer_;

    std::shared_lock<std::shared_mutex> running_lock{running_mut};
    while (running)
    {
        running_lock.unlock();
        uint32_t bitmask = 0;
        uint32_t set_points = 0;

        auto [frame, err3] = streamer_.read();

        // EOF just means that we are stopping gracefully.
        if (err3.type == "freighter.eof")
        {
            return freighter::TYPE_NIL;
        }
        if (!err3.ok())
        {
            std::cerr << err3.message() << std::endl;
            return err3;
        }

        for (size_t i = 0; i < frame.size(); i++)
        {
            auto &key = (*frame.columns)[i];
            auto &series = (*frame.series)[i];
            // find the index of the key in keys
            auto it = std::find(keys.begin(), keys.end(), key);
            if (it != keys.end())
            {
                // if the key is found, set the bit in the bitmask
                bitmask |= 1 << (it - keys.begin());
                // set the bit in the set_points
                uint8_t set_point;
                memcpy(&set_point, series.data.get(), 1);

                if (set_point > 0)
                    set_points |= 1 << (it - keys.begin());
            }
        }

        std::unique_lock<std::mutex> writer_lock{writer_mut};
        auto res = daq->writeDigital(bitmask, set_points);
        writer_lock.unlock();

        auto ack = synnax::Frame(N_VALVES + 1);

        ack.add(ack_time.key, synnax::Series(std::vector<int64_t>{synnax::TimeStamp::now().value}));

        // For each valve.
        for (int i = 0; i < N_VALVES; i++)
        {
            // Determine if we should send an ack.
            if ((res & (1 << i)) > 0)
                ack.add(acks[i].key, synnax::Series(std::vector<uint8_t>{1}));
            else
                ack.add(acks[i].key, synnax::Series(std::vector<uint8_t>{0}));
        }
        // TODO: Handle this externally.
        if (!writer->write(std::move(ack)))
            return writer->error();

        std::unique_lock<std::shared_mutex> acked_lock{acked_mut};
        acked = true;
        acked_lock.unlock();

        running_lock.lock();
    }
    running_lock.unlock();

    commit_thread.join();

    return freighter::TYPE_NIL;
}