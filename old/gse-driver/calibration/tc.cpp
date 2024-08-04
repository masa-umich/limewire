#include "calibration.h"

// DEPRECATED Used to convert mV to Celsius
float computeTemperature(float mv)
{
    // Type T equations
    // mv = voltage in mV
    // Returns computed temperature in Celsius
    float T0, V0, p1, p2, p3, p4, q1, q2, q3;
    if (-6.3 <= mv && mv < -4.648)
    {
        T0 = (float)-1.9243000E+02;
        V0 = (float)-5.4798963E+00;
        p1 = (float)5.9572141E+01;
        p2 = (float)1.9675733E+00;
        p3 = (float)-7.8176011E+01;
        p4 = (float)-1.0963280E+01;
        q1 = (float)2.7498092E-01;
        q2 = (float)-1.3768944E+00;
        q3 = (float)-4.5209805E-01;
    }
    else if (-4.648 <= mv && mv < 0.0)
    {
        T0 = (float)-6.0000000E+01;
        V0 = (float)-2.1528350E+00;
        p1 = (float)3.0449332E+01;
        p2 = (float)-1.2946560E+00;
        p3 = (float)-3.0500735E+00;
        p4 = (float)-1.9226856E-01;
        q1 = (float)6.9877863E-03;
        q2 = (float)-1.0596207E-01;
        q3 = (float)-1.0774995E-02;
    }
    else if (0.0 <= mv && mv < 9.288)
    {
        T0 = (float)1.3500000E+02;
        V0 = (float)5.9588600E+00;
        p1 = (float)2.0325591E+01;
        p2 = (float)3.3013079E+00;
        p3 = (float)1.2638462E-01;
        p4 = (float)-8.2883695E-04;
        q1 = (float)1.7595577E-01;
        q2 = (float)7.9740521E-03;
        q3 = (float)0.0;
    }
    else if (9.288 <= mv && mv < 20.872)
    {
        T0 = (float)3.0000000E+02;
        V0 = (float)1.4861780E+01;
        p1 = (float)1.7214707E+01;
        p2 = (float)-9.3862713E-01;
        p3 = (float)-7.3509066E-02;
        p4 = (float)2.9576140E-04;
        q1 = (float)-4.8095795E-02;
        q2 = (float)-4.7352054E-03;
        q3 = (float)0;
    }
    else
    {
        return -1;
    }
    auto numerator = ((mv - V0) * (p1 + (mv - V0) * (p2 + (mv - V0) * (p3 + p4 * (mv - V0)))));
    auto denominator = (1 + (mv - V0) * (q1 + (mv - V0) * (q2 + q3 * (mv - V0))));
    return (T0 + (numerator / denominator));
}

void Calibration::TC::transform(std::vector<float> &data, size_t start, size_t end)
{
    // Do nothing
}
