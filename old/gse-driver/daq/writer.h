#pragma once

#include <vector>
#include "comedilib.h"
#include "daq_mappings.h"
#include <memory>
#include <stdlib.h>
#include "comedi_device.h"

namespace DAQ
{

    /// @brief interface for a writable GSE DAQ.
    class Writer
    {
    public:
        Writer();
        virtual ~Writer();

        /// @brief sets digital output values on the GSE DAQ.
        /// @param bitmask a 32-bit mask representing the set points that should be
        /// changed by the DAQ.
        /// @param set_points a 32-bit mask representing the values that should be set
        /// for the corresponding bits in the bitmask.
        /// @return uint32_t a 32-bit field containing the digital output ACK from each
        /// digitial output channel.
        virtual uint32_t writeDigital(uint32_t bitmask, uint32_t set_points);

    private:
        const char *DIGITAL_FILENAME = "/dev/comedi0";
        const int DIGITAL_WRITE_SUBDEV = 1;

        Comedi_Device *digital_device;

        uint32_t enabled_states = 0x0;
    };
};
