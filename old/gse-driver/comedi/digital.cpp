#include <iostream>
#include <boost/asio.hpp>
#include <boost/bind/bind.hpp>
#include "gse-driver/comedi/digital.hpp"
#include "gse-driver/comedi/comedilib.h"

#include <stdio.h>		
#include <stdlib.h>
#include <ctype.h>

using namespace std;

int READ_SUBDEV = 0;
int WRITE_SUBDEV = 1;
const char FILENAME[] = "/dev/comedi0";

const int FREQUENCY = 100; // HZ
const int timerWait = 1 / FREQUENCY * 1000; // milliseconds 

void getDigitalCB (const boost::system::error_code& /*e*/, boost::asio::steady_timer* t, comedi_t *device)
{
	int retval;
	unsigned int bits = 0;
	unsigned int * bits_ptr = &bits; 
	unsigned int write_mask = 0;
	
	if (device == NULL) {
		comedi_perror(FILENAME);
	//	return 1;
	}
		
	retval = comedi_dio_bitfield2(device, READ_SUBDEV, write_mask, bits_ptr, 0);
        std::cout << bits << endl;	

	if (retval < 0) {
		comedi_perror(FILENAME);
	//	return 1;
	}

	write_mask = 4294967295;
	retval = comedi_dio_bitfield2(device, WRITE_SUBDEV, write_mask, bits_ptr, 0);

	if (retval < 0) {
		comedi_perror(FILENAME);
	//	return 1;
	}
	t->expires_at(t->expiry() + boost::asio::chrono::milliseconds(timerWait));
    	t->async_wait(boost::bind(getDigitalCB,
          boost::asio::placeholders::error, t, device));
}

int main()
{
  
	/* Comedi Setup */
	comedi_t *device;
	device = comedi_open(FILENAME);


	/* Boost Setup */
  	boost::asio::io_context io;

  	boost::asio::steady_timer t(io, boost::asio::chrono::milliseconds(timerWait));
 	 t.async_wait(boost::bind(getDigitalCB,
        	boost::asio::placeholders::error, &t, device));

  	io.run();

  	return 0;
}
