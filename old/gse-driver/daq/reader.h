#pragma once

#include <vector>
#include "comedilib.h"
#include "daq_mappings.h"
#include "comedi_device.h"
#include "matrix.h"
#include <boost/asio.hpp>
#include <boost/bind/bind.hpp>
#include <memory>
#include <thread>

namespace DAQ
{

#define N 200 // TODO temp

    /// @brief interface for a readable GSE DAQ
    class Reader
    {
    public:
        /// @brief acquires digital samples from the GSE DAQ.
        virtual void readDigital(std::shared_ptr<std::vector<uint32_t>> data, std::shared_ptr<std::vector<int64_t>> times);

        /// @brief acquires analog samples from the daq.
        virtual void readAnalog(std::shared_ptr<Matrix<float>> data, std::shared_ptr<std::vector<int64_t>> times);

        /// TODO: Add descriptions.
        void start();
        void stop();

        /// Constructor / Destructor
        Reader();
        virtual ~Reader();

    private:
        /// TODO: Add descriptions.
        void startDigitalCollection();
        void startAnalogCollection();
        void stopDigitalCollection();
        void stopAnalogCollection();
        int prepareCmdLib(comedi_t *dev, int subdevice, int n_scan,
                          int n_chan, unsigned scan_period_nanosec,
                          comedi_cmd *cmd);

        float convertDatum(lsampl_t raw, int channel_index)
        {
            return (float)comedi_to_physical(raw, &(poly_list[DAQ_CHANNELS[channel_index]]));
        }

        // ANALOG READ UTILS
        void waitForBufferToFill(comedi_t *dev, std::shared_ptr<std::vector<std::int64_t>> times);
        int readFromAnalogDevice(comedi_t *dev, char *buffer, const int BUFSZ);
        void convertAndFillData(char *buf, std::shared_ptr<Matrix<float>> data);
        void handleReadError(int ret);

        // DIGITAL READ UTILS
        int readFromDigitalDevice();

        int analog_subdev_flags = 0;

        // CONFIG

        const char DIGITAL_FILENAME[13] = "/dev/comedi0";
        const char ANALOG_FILENAME[13] = "/dev/comedi1";

        const int DIGITAL_READ_SUBDEV = 0;
        const int ANALOG_READ_SUBDEV = 0;

        const int ANALOG_BASE_CHAN = 0;

        comedi_cmd a_cmd;

        int bytes_per_analog_sample = 4;

        const int DIGITAL_FREQUENCY = 1; // Hz
        const int ANALOG_FREQUENCY = 200; // Hz

        Comedi_Device *analog_device;
        Comedi_Device *digital_device;

        // Calibration stuff
        comedi_calibration_t *parsed_calibration; // NEEDS to be freed when stopping analog collection
        comedi_polynomial_t poly_list[4]; // index refers to comedi range (0-3)
        const char* CAL_FILE_PATH = "/usr/local/var/lib/comedi/calibrations/ni_pcimio_pci-6225_comedi1";

        const static int BUFSZ = 80 * (ANALOG_N) * sizeof(sampl_t);
        sampl_t buf[BUFSZ];

        static unsigned int chanlist[N_CHANS];
        static comedi_range *range_info[N_CHANS];
        static lsampl_t maxdata[N_CHANS];

        std::string cmdtest_messages[6] = {
            "success",
            "invalid source",
            "source conflict",
            "invalid argument",
            "argument conflict",
            "invalid chanlist",
        };
    };

};
