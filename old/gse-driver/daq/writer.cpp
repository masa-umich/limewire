#include "writer.h"
#include "comedilib.h"
#include "iostream"
#include <boost/asio.hpp>
#include <boost/bind/bind.hpp>

namespace DAQ
{

	Writer::Writer() {
		digital_device = new Comedi_Device();
	}

	uint32_t Writer::writeDigital(uint32_t bitmask, uint32_t setpoints)
	{

		// Setpoints uses inverted logic
		uint32_t bitfield_input = ~setpoints;

		comedi_t *d_device;

		d_device = digital_device->open(DIGITAL_FILENAME);

		// retval indicates success status of function execution
		int retval = comedi_dio_bitfield2(d_device, DIGITAL_WRITE_SUBDEV, bitmask, &bitfield_input, 0);

		if (retval < 0)
		{
			comedi_perror(DIGITAL_FILENAME);
		} else { // Command successfully executed

			// Update enabled states
			enabled_states &= ~bitmask;
			enabled_states |= (setpoints & bitmask);
		}

		digital_device->close(DIGITAL_FILENAME);

		return enabled_states;
	}

	Writer::~Writer() {
		delete digital_device;
	}

};
