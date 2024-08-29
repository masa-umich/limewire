#include <stdio.h>
#include "gse-driver/comedi/comedilib.h"
#include <fcntl.h>
#include <unistd.h>
#include <sys/time.h>
#include <errno.h>
#include <stdlib.h>
#include <string.h>

extern comedi_t *device;

struct parsed_options {
	char *filename;
	double value;
	int subdevice;
	int channel;
	int aref;
	int range;
	int verbose;
	int n_chan;
	int n_scan;
	double freq;
};

int prepare_cmd_lib(comedi_t *dev, int subdevice, int n_scan,
		    int n_chan, unsigned period_nanosec,
		    comedi_cmd *cmd);

void do_cmd(comedi_t *dev,comedi_cmd *cmd);

double * readAnalog ();

void print_datum(lsampl_t raw, int channel_index);

