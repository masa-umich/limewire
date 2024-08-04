/// GTest.
#include <gtest/gtest.h>

/// Internal.
#include "gse-driver/calibration/calibration.h"


/// @brief it should correctly convert millivolt values to TC readings.
TEST(CalibrationTests, testTC) {
    Calibration::Calibrator *cal = new Calibration::TC();
    std::vector<float> mv = {-6.10, -4.419, -2.153, 0, 1.196, 3.814, 5.228, 8.237, 9.228, 9.876};
    std::vector<float> temps = {-240, -140, -60, 0, 30, 90, 120, 180, 200, 210};
    cal->transform(mv, 0, mv.size());
    // Iterate through the transformed data, asserting that each output value falls
    // within 2.0 degrees of the expected value.
    for (int i = 0; i < mv.size(); i++) ASSERT_NEAR(mv[i], temps[i], 1.5);
}
