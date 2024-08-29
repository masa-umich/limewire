#include <stdio.h>
#include "gse-driver/comedi/comedilib.h"
#include <fcntl.h>
#include <unistd.h>
#include <sys/time.h>
#include <errno.h>
#include <stdlib.h>
#include <string.h>
#include <string>
#include "gse-driver/comedi/analog.h"

#define BUFSZ 10000
char buf[BUFSZ];

#define N_CHANS 256
static unsigned int chanlist[N_CHANS];
static comedi_range * range_info[N_CHANS];
static lsampl_t maxdata[N_CHANS];

std::string cmdtest_messages[] ={
        "success",
        "invalid source",
        "source conflict",
        "invalid argument",
        "argument conflict",
        "invalid chanlist",
};

double * readAnalog (int n_chan, double freq, int n_scan)
{
	comedi_t *dev;
	comedi_cmd c,*cmd = &c;
	int ret;
	int total = 0;
	int col;
	int i;
	int subdev_flags;
	lsampl_t raw;

	struct parsed_options options;
	
	std::string filename = "/dev/comedi1";
	char[filename.size() + 1] c_filename;
	
	memset(&options, 0, sizeof(options));
	options.filename = filename.c_str();
	options.subdevice = 0;
	options.channel = 0;
	options.range = 0;
	options.aref = AREF_GROUND;
	options.n_chan = n_chan;
	options.n_scan = n_scan;
	options.freq = freq;

	/* open the device */
	dev = comedi_open(options.filename);
	if (!dev) {
		comedi_perror(options.filename);
		exit(1);
	}

	/* Print numbers for clipped inputs */
	comedi_set_global_oor_behavior(COMEDI_OOR_NUMBER);

	/* Set up channel list */
	for (i = 0; i < options.n_chan; i++) {
		chanlist[i] =
			CR_PACK(options.channel + i, options.range,
				options.aref);
		range_info[i] =
			comedi_get_range(dev, options.subdevice,
					 options.channel, options.range);
		maxdata[i] =
			comedi_get_maxdata(dev, options.subdevice,
					   options.channel);
	}

	/* prepare_cmd_lib() uses a Comedilib routine to find a
	 * good command for the device.  prepare_cmd() explicitly
	 * creates a command, which may not work for your device. */
	prepare_cmd_lib(dev, options.subdevice, options.n_scan,
			options.n_chan, 1e9 / options.freq, cmd);

	/* comedi_command_test() tests a command to see if the
	 * trigger sources and arguments are valid for the subdevice.
	 * If a trigger source is invalid, it will be logically ANDed
	 * with valid values (trigger sources are actually bitmasks),
	 * which may or may not result in a valid trigger source.
	 * If an argument is invalid, it will be adjusted to the
	 * nearest valid value.  In this way, for many commands, you
	 * can test it multiple times until it passes.  Typically,
	 * if you can't get a valid command in two tests, the original
	 * command wasn't specified very well. */
	ret = comedi_command_test(dev, cmd);
	if (ret < 0) {
		comedi_perror("comedi_command_test");
		if(errno == EIO){
			fprintf(stderr,
				"Ummm... this subdevice doesn't support commands\n");
		}
		exit(1);
	}
	ret = comedi_command_test(dev, cmd);
	if (ret < 0) {
		comedi_perror("comedi_command_test");
		exit(1);
	}
	fprintf(stderr,"second test returned %d (%s)\n", ret,
		cmdtest_messages[ret]);
	if (ret != 0) {
		fprintf(stderr, "Error preparing command\n");
		exit(1);
	}

	/* comedi_set_read_subdevice() attempts to change the current
	 * 'read' subdevice to the specified subdevice if it is
	 * different.  Changing the read or write subdevice might not be
	 * supported by the version of Comedi you are using.  */
	comedi_set_read_subdevice(dev, cmd->subdev);
	/* comedi_get_read_subdevice() gets the current 'read'
	 * subdevice. if any.  This is the subdevice whose buffer the
	 * read() call will read from.  Check that it is the one we want
	 * to use.  */
	ret = comedi_get_read_subdevice(dev);
	if (ret < 0 || ret != cmd->subdev) {
		fprintf(stderr,
			"failed to change 'read' subdevice from %d to %d\n",
			ret, cmd->subdev);
		exit(1);
	}

	/* start the command */
	ret = comedi_command(dev, cmd);
	if (ret < 0) {
		comedi_perror("comedi_command");
		exit(1);
	}
	subdev_flags = comedi_get_subdevice_flags(dev, options.subdevice);
	col = 0;
	while (1) {
		ret = read(comedi_fileno(dev),buf,BUFSZ);
		if (ret < 0) {
			/* some error occurred */
			perror("read");
			break;
		} else if (ret == 0) {
			/* reached stop condition */
			break;
		} else {
			int bytes_per_sample;

			total += ret;
			if (options.verbose) {
				fprintf(stderr, "read %d %d\n", ret,
					total);
			}
			if (subdev_flags & SDF_LSAMPL) {
				bytes_per_sample = sizeof(lsampl_t);
			} else {
				bytes_per_sample = sizeof(sampl_t);
			}
			for (i = 0; i < ret / bytes_per_sample; i++) {
				if (subdev_flags & SDF_LSAMPL) {
					raw = ((lsampl_t *)buf)[i];
				} else {
					raw = ((sampl_t *)buf)[i];
				}
				print_datum(raw, col);
				col++;
				if (col == options.n_chan) {
					printf("\n");
					col=0;
				}
			}
		}
	}

	return 0;
}

/*
 * This prepares a command in a pretty generic way.  We ask the
 * library to create a stock command that supports periodic
 * sampling of data, then modify the parts we want.
 */
int prepare_cmd_lib(comedi_t *dev, int subdevice, int n_scan,
		    int n_chan, unsigned scan_period_nanosec,
		    comedi_cmd *cmd)
{
	int ret;

	memset(cmd,0,sizeof(*cmd));

	/* This comedilib function will get us a generic timed
	 * command for a particular board.  If it returns -1,
	 * that's bad. */
	ret = comedi_get_cmd_generic_timed(dev, subdevice, cmd, n_chan,
					   scan_period_nanosec);
	if (ret < 0) {
		fprintf(stderr,
			"comedi_get_cmd_generic_timed failed\n");
		return ret;
	}

	/* Modify parts of the command */
	cmd->chanlist = chanlist;
	cmd->chanlist_len = n_chan;
	if (cmd->stop_src == TRIG_COUNT) {
		cmd->stop_arg = n_scan;
	}

	return 0;
}

void print_datum(lsampl_t raw, int channel_index)
{
	double physical_value;

	physical_value = comedi_to_phys(raw, range_info[channel_index],
					maxdata[channel_index]);
	printf("%#8.6g ", physical_value);
}

void stringToCString (std::string s, char* c)
{
	for (int i = 0; i < s.size(); i++){
		c[i] = s.at(i);
	}
	c[s.size()] = '\0';
}
