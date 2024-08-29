/// GTest.
#include <gtest/gtest.h>

/// Internal
#include "gse-driver/calibration/calibration.h"

/// @brief it should calibrate voltage values to pressure values.
TEST(CalibrationTests, testPressure) {
    // Offset of 500 mv and scale of 250psi/v
    Calibration::Calibrator *cal = new Calibration::PT(0.5, 250);
    std::vector<float> volts = {0.5, 4.5};
    std::vector<float> pressures = {0.0, 1000};
    cal->transform(volts, 0, volts.size());
    // Iterate through the transformed data, asserting that each output value falls
    // within 0.1 degrees of the expected value.
    for (int i = 0; i < volts.size(); i++) ASSERT_NEAR(volts[i], pressures[i], 0.1);
}

TEST(CalibrationTests, testAmbientization) {
    // Offset of 500 mv and scale of 4mv/psi. Set for a 1000 psi max PT.
    Calibration::Calibrator *cal = new Calibration::PT(0.5, 250);
    std::vector<float> volts = {0.504, 0.504};
    std::vector<float> pressures = {1.0, 1.0};
    cal->transform(volts, 0, volts.size());
    for (int i = 0; i < volts.size(); i++) ASSERT_NEAR(volts[i], pressures[i], 0.1);
    // Adjust it up by the ambient volt offset.
    volts = {0.508, 0.508};
    cal->transform(volts, 0, volts.size());
    for (int i = 0; i < volts.size(); i++) ASSERT_NEAR(volts[i], pressures[i], 0.1);
}
