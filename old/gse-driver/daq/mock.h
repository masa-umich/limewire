#pragma once

/// std.
#include <memory>
#include <vector>
#include <cstddef>
#include <stddef.h>

/// Locals.
#include "gse-driver/daq/matrix.h"
#include "gse-driver/daq/reader.h"
#include "gse-driver/daq/writer.h"

namespace DAQ
{

    class mockWriter : public Writer
    {
    public:
        /// @brief Simply writes to a vector, which can be viewed for testing
        uint32_t writeDigital(uint32_t bitmask, uint32_t set_points) override
        {
            // Zero out valves where bitmask is set.
            valves &= ~bitmask;

            // Zero out set point in positions where bitmask is zero.
            set_points &= bitmask;

            // Now, we can or, keeps original values and sets new ones.
            valves |= set_points;

            // Return the state of system.
            return valves;
        }

        /// @brief uint32_t to test with
        uint32_t valves = 0;
    };
    class mockReader : public Reader
    {
    public:
        /// @brief fills data with all 1s, times incrementing from 0 - sz of times
        void readDigital(std::shared_ptr<std::vector<uint32_t>> data, std::shared_ptr<std::vector<int64_t>> times) override
        {
            for (auto &datum : *data)
            {
                datum = 1;
            }
            for (size_t i = 0; i < times->size(); i++)
            {
                times->at(i) = (int64_t)i;
            }
        }

        /// @brief fills data with all 1s, times incrementing from 0 - sz of times
        void readAnalog(std::shared_ptr<Matrix<float>> data, std::shared_ptr<std::vector<int64_t>> times) override
        {
            auto [n, m] = data->size();
            for (size_t i = 0; i < n; i++)
            {
                for (size_t j = 0; j < m; j++)
                {
                    data->at(i, j) = 1;
                }
            }
            for (size_t i = 0; i < times->size(); i++)
            {
                times->at(i) = (int64_t)i;
            }
        }
    };
}