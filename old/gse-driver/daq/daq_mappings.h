#include <cstdint>
#pragma once

/* PCI-6225 range mapping for AIN channels
range: 0, min : -10.000000, max : 10.000000, unit : 0
range : 1, min : -5.000000, max : 5.000000, unit : 0
range : 2, min : -1.000000, max : 1.000000, unit : 0
range : 3, min : -0.200000, max : 0.200000, unit : 0
*/

#define DEBUG true

#define N_CHANS 80
#define N_VALVES 24
#define ANALOG_N 5
#define DIGITAL_N 1

// _ Appended since there are functions with these names, and compiler replaces function names with the numbers if
// not distinguished.
#define PT_ 1
#define TC_ 1
#define LC_ 1
#define CURR 1

const std::uint8_t DAQ_CHANNELS[N_CHANS] = {

	// 36 Pressure Transducer Channels
	PT_,
	PT_,
	PT_,
	PT_,
	PT_,
	PT_,
	PT_,
	PT_,
	PT_,
	PT_,
	PT_,
	PT_,
	PT_,
	PT_,
	PT_,
	PT_,
	PT_,
	PT_,
	PT_,
	PT_,
	PT_,
	PT_,
	PT_,
	PT_,
	PT_,
	PT_,
	PT_,
	PT_,
	PT_,
	PT_,
	PT_,
	PT_,
	PT_,
	PT_,
	PT_,
	PT_,

	// 24 Solenoid Valve Current Channels
	CURR,
	CURR,
	CURR,
	CURR,
	CURR,
	CURR,
	CURR,
	CURR,
	CURR,
	CURR,
	CURR,
	CURR,
	CURR,
	CURR,
	CURR,
	CURR,
	CURR,
	CURR,
	CURR,
	CURR,
	CURR,
	CURR,
	CURR,
	CURR,

	// One more PT because ATLO :(
	PT_,

	// 3 Load Cell Channels
	LC_,
	LC_,
	LC_,

	// 16 Thermocouple Channels
	TC_,
	TC_,
	TC_,
	TC_,
	TC_,
	TC_,
	TC_,
	TC_,
	TC_,
	TC_,
	TC_,
	TC_,
	TC_,
	TC_,
	TC_,
	TC_};
