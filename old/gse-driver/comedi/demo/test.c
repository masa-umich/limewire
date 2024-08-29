/*
 * Multi-channel, multi-range one-shot input demo
 * Part of Comedilib
 *
 * Copyright (c) 1999,2000 David A. Schleef <ds@schleef.org>
 *
 * This file may be freely modified, distributed, and combined with
 * other software, as long as proper attribution is given in the
 * source code.
 */
/*
   This demo opens /dev/comedi0 and looks for an analog input
   subdevice.  If it finds one, it measures one sample on each
   channel for each input range.  The value NaN indicates that
   the measurement was out of range.
 */

#include <stdio.h>
#include "comedilib.h"
#include <fcntl.h>
#include <unistd.h>
#include <stdlib.h>
#include <errno.h>
#include <getopt.h>
#include <ctype.h>
#include "examples.h"

comedi_t *device;
static char * const default_filename = "/dev/comedi0";

int main(int argc, char *argv[])
{
	int chan;
	int n_ranges;
	int range;
	int maxdata;
	lsampl_t data;
	double voltage;

	static char * const default_filename = "/dev/comedi0"

	struct parsed_options options;

        memset(&options, 0, sizeof(options));
        options.filename = "/dev/comedi0";
        options.subdevice = 0;
        options.channel = 0;
        options.range = 0;
        options.aref = AREF_GROUND;
        options.n_chan = 1;
        options.n_scan = 10000;
        options.freq = 1000.0;	
	device = comedi_open(options.filename);
	if(!device){
		comedi_perror(options.filename);
		exit(-1);
	}

	for(chan = 0; chan < options.n_chan; ++chan){
		printf("%d: ", chan);

		n_ranges = comedi_get_n_ranges(device, options.subdevice, chan);

		maxdata = comedi_get_maxdata(device, options.subdevice, chan);
		for(range = 0; range < n_ranges; range++){
			comedi_data_read(device, options.subdevice, chan, range, options.aref, &data);
			voltage = comedi_to_phys(data, comedi_get_range(device, options.subdevice, chan, range), maxdata);
			printf("%g ", voltage);
		}
		printf("\n");
	}
	return 0;
}

