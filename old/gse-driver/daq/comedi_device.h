/*

	Class to wrap comedi device handling.

*/

#pragma once

#ifndef COMEDI_DEVICE_H
#define COMEDI_DEVICE_H

#include <mutex>
#include "comedilib.h"
#include "iostream"

namespace DAQ {
	

	class Comedi_Device {
	public:
				
		comedi_t* open(const char* filename) {

			//dev_mu.lock();
	
			dev = comedi_open(filename);
			if (dev == NULL) {
				comedi_perror(filename);
			}

			return dev;
		}

		void close(const char* filename) {

			int retval = comedi_close(dev);
			if (retval < 0) {
				comedi_perror(filename);
			}

			//dev_mu.unlock();
		}

		comedi_t* dev;

	private:
		static std::mutex dev_mu;	
	

	};

}

#endif
