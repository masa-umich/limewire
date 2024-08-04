#pragma once

#include <vector>
#include <stddef.h>
#include <iostream>

namespace Calibration {
class Calibrator {
public:
    /// @brief applies a calibration to the given vector of data, replacing the
    /// original values with the calibrated values.
    /// @modifies data, replacing the original values with the calibrated values.
    virtual void transform(std::vector<float> &data, size_t start, size_t end) = 0;
};

class PT : public Calibrator {
private:
    /// @brief a millivolt offset to be subtracted from the raw data.
    float offset;
    /// @brief a scale that represents the number of millivolts per psi.
    float scale;
    /// @brief an internally set offset that marks the raw data value of the
    /// ambient pressure. Triggered whenever the calibrator is created.
    float ambient;
    /// @brief whether or not the ambient value has been set.
    bool ambient_set;

public:
    PT(float offset, float scale) : offset(offset), scale(scale), ambient(0), ambient_set(false) {}

    /// @brief implements the calibration for a pressure transducer.
    void transform(std::vector<float> &data, size_t start, size_t end) override {
        if (ambient_set) {
            for (size_t i = start; i < end; i++)
           	data[i] = ((data[i] - offset) * scale) - ambient;
	    
            return;
        }

        ambient = 0;
        for (size_t i = start; i < end; i++) {
            data[i] = (data[i] - offset) * scale;
            ambient += data[i];
        }
        ambient /= (end - start);
        std::cout << "Ambient pressure: " << ambient << std::endl;
        ambient_set = true;
    }
};

class TC : public Calibrator {
private:

public:

    void transform(std::vector<float>& data, size_t start, size_t end) override;

};

class NOOP : public Calibrator {
public:
    /// @brief implements the calibration for CURR or LC.
    void transform(std::vector<float> &data, size_t start, size_t end) override {
        return;
    }
};

}
