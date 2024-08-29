#include "reader.h"
#include "comedilib.h"
#include "iostream"

#include <thread>
#include <vector>
#include <chrono>
#include <functional>

#include <boost/asio/basic_waitable_timer.hpp>

#ifdef _WINDOWS
#include <io.h>
#else
#include <unistd.h>
#endif

namespace DAQ
{
	// Definition of Static Variables
	unsigned int Reader::chanlist[N_CHANS];
	comedi_range *Reader::range_info[N_CHANS];
	lsampl_t Reader::maxdata[N_CHANS];

	int64_t getTimestamp();
	/// @brief acquires digital samples from the GSE DAQ.
	void Reader::readDigital(std::shared_ptr<std::vector<uint32_t>> data, std::shared_ptr<std::vector<std::int64_t>> times)
	{

		int timerWait = static_cast<int>(1 / DIGITAL_FREQUENCY * 1000);

		boost::asio::io_context io;

		for (int i = 0; i < DIGITAL_N; ++i)
		{

			boost::asio::deadline_timer t(io, boost::posix_time::milliseconds(timerWait));

			int64_t timestamp = getTimestamp();

			int bits = readFromDigitalDevice();

			(*data)[i] = bits;
			(*times)[i] = timestamp;

			if (i == DIGITAL_N - 1)
			{
				break; // save time on last wait
			}

			t.wait(); // Wait for timer to expire for next read
		}
	}

	/// @brief acquires analog samples from the daq.
	void Reader::readAnalog(std::shared_ptr<Matrix<float>> data, std::shared_ptr<std::vector<int64_t>> times)
	{
		comedi_t *a_device = analog_device->dev;

		int ret = 0;

		// Start async command then do other stuff while we wait
		ret = comedi_command(a_device, &a_cmd);

		if (ret < 0)
		{
			comedi_perror("comedi_command");
			exit(1);
		}

		int64_t initial_time = getTimestamp();
		(*times)[0] = initial_time;

		for (int i = 1; i < ANALOG_N; ++i)
		{
			(*times)[i] = initial_time + (int64_t)(1e9 / ANALOG_FREQUENCY) * i;
		}

		size_t row = -1; // loop starts with row++ lmao :despair:
		size_t col = 0;

		int comedi_fileno_ = comedi_fileno(a_device);

		while (1)
		{
			int ret = read(comedi_fileno_, buf, BUFSZ);

			if (ret < 0)
			{
				/* some error occurred */
				perror("read");
				break;
			}
			else if (ret == 0) {
				// EOF
				printf("%ld EOF\n", col);

			}
			else if (ret > 0)
			{

				for (size_t i = 0; i < static_cast<size_t>(ret / bytes_per_analog_sample); ++i)
				{
					++row;

					if (row == (N_CHANS))
					{
						col++;

						if (col == ANALOG_N)
						{
							break;
						}
						row = 0;
					}

					sampl_t datum = ((sampl_t *)buf)[col * N_CHANS + row];
					data->at(row, col) = convertDatum(datum, col);
				}
			}

			if (col >= ANALOG_N - 1)
			{
				break;
			}
		}

		/*
		* Condition readings
		*/

		// TC "Oversampling" -- Channels 64-79 (last 16)
		for (int i = N_CHANS - 16; i < N_CHANS; ++i) {
			double sum = 0;
			for (int j = 0; j < ANALOG_N; ++j) {
				sum += (double) data->at(i, j);
			}

			// TEMP TODO Fix --> integrate with Synnax Cals eventually
			// TC Convert V to C
			double avg = (sum / ANALOG_N);
			avg = ((avg / 5.0) * 250) - 200; // Assume all converters are -200 to +50c and convert this way TODO FIX
			for (int j = 0; j < ANALOG_N; ++j) {
				data->at(i, j) = (float)avg;
			}


		}

		// Cancel previous command
		ret = comedi_cancel(a_device, ANALOG_READ_SUBDEV);
		if (ret < 0)
		{
			comedi_perror("comedi_cancel");
			exit(1);
		}
	}

	/*
	 * Starts data collection, continously adds data to digital_samples and analog_samples.
	 */
	void Reader::start()
	{
		std::cout << "Starting Collection" << std::endl;

		startAnalogCollection();
		startDigitalCollection();
	}

	/*
	 * Stops data collection, empties digital_samples and analog_samples
	 */
	void Reader::stop()
	{
		std::cout << "Stopping Collection" << std::endl;

		stopAnalogCollection();
		stopDigitalCollection();
	}

	// Constructor and Destructor

	Reader::Reader()
	{

		analog_device = new Comedi_Device();
		digital_device = new Comedi_Device();
	}

	Reader::~Reader()
	{
		delete analog_device;
		delete digital_device;
	}

	void Reader::startDigitalCollection()
	{

		std::cout << "starting digital collection" << std::endl;

		digital_device->open(DIGITAL_FILENAME);
	}

	void Reader::startAnalogCollection()
	{
		std::cout << "starting analog collection" << std::endl;

		/* open the device
			device can stay open
		*/
		comedi_t *a_device = analog_device->open(ANALOG_FILENAME);

		/* Print numbers for clipped inputs */
		comedi_set_global_oor_behavior(COMEDI_OOR_NUMBER);

		/* Set up channel list */
		for (int i = 0; i < N_CHANS; i++)
		{
			chanlist[i] = CR_PACK(ANALOG_BASE_CHAN + i, DAQ_CHANNELS[i], AREF_GROUND);
			range_info[i] = comedi_get_range(a_device, ANALOG_READ_SUBDEV, ANALOG_BASE_CHAN + i, DAQ_CHANNELS[i]);
			maxdata[i] = comedi_get_maxdata(a_device, ANALOG_READ_SUBDEV, ANALOG_BASE_CHAN + i);
		}

		/* prepare_cmd_lib() uses a Comedilib routine to find a
		 * good command for the device.  prepare_cmd() explicitly
		 * creates a command, which may not work for your device. */
		// n_scan unused
		prepareCmdLib(a_device, ANALOG_READ_SUBDEV, ANALOG_N, N_CHANS, (unsigned int)1e9 / ANALOG_FREQUENCY, &a_cmd);

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
		int ret = comedi_command_test(a_device, &a_cmd);
		if (ret < 0)
		{
			comedi_perror("comedi_command_test");
			exit(1);
		}

		/* comedi_set_read_subdevice() attempts to change the current
		 * 'read' subdevice to the specified subdevice if it is
		 * different.  Changing the read or write subdevice might not be
		 * supported by the version of Comedi you are using.  */
		comedi_set_read_subdevice(a_device, ANALOG_READ_SUBDEV);
		/* comedi_get_read_subdevice() gets the current 'read'
		 * subdevice. if any.  This is the subdevice whose buffer the
		 * read() call will read from.  Check that it is the one we want
		 * to use.  */
		ret = comedi_get_read_subdevice(a_device);
		if (ret < 0 || ret != (int)a_cmd.subdev)
		{
			std::cerr << "failed to change 'read' subdevice from " << ret << " to " << a_cmd.subdev << std::endl;
			exit(1);
		}

		analog_subdev_flags = comedi_get_subdevice_flags(a_device, ANALOG_READ_SUBDEV);

		if (analog_subdev_flags & SDF_LSAMPL)
		{
			bytes_per_analog_sample = sizeof(lsampl_t);
		}
		else
		{
			bytes_per_analog_sample = sizeof(sampl_t);
		}

		/*
		 *	Apply calibration info
		 */
		parsed_calibration = comedi_parse_calibration_file(CAL_FILE_PATH);

		for (int range = 0; range < 4; ++range)
		{
			ret += comedi_get_softcal_converter(ANALOG_READ_SUBDEV, ANALOG_BASE_CHAN, range, COMEDI_TO_PHYSICAL, parsed_calibration, &(poly_list[range]));
		}

		if (ret < 0)
		{
			comedi_perror("comedi_get_softcal_converter");
			exit(1);
		}
	}

	void Reader::stopAnalogCollection()
	{

		analog_device->close(ANALOG_FILENAME);

		comedi_cleanup_calibration(parsed_calibration);
	}

	void Reader::stopDigitalCollection()
	{

		digital_device->close(DIGITAL_FILENAME);
	}

	int64_t getTimestamp()
	{
		return (int64_t)std::chrono::time_point_cast<std::chrono::nanoseconds>(std::chrono::system_clock::now()).time_since_epoch().count();
	}

	/*
	 * This prepares a command in a pretty generic way.  We ask the
	 * library to create a stock command that supports periodic
	 * sampling of data, then modify the parts we want.
	 */
	int Reader::prepareCmdLib(comedi_t *dev, int subdevice, int n_scan,
							  int n_chan, unsigned scan_period_nanosec,
							  comedi_cmd *cmd)
	{
		int ret;

		memset(cmd, 0, sizeof(*cmd));

		/* This comedilib function will get us a generic timed
		 * command for a particular board.  If it returns -1,
		 * that's bad. */
		ret = comedi_get_cmd_generic_timed(dev, subdevice, cmd, n_chan,
										   scan_period_nanosec);
		if (ret < 0)
		{
			std::cerr << "comedi_get_cmd_generic_timed failed" << std::endl;
			return ret;
		}

		/* Modify parts of the command */
		cmd->chanlist = chanlist;
		cmd->chanlist_len = n_chan;
		if (cmd->stop_src == TRIG_COUNT)
		{
			cmd->stop_arg = n_scan;
		}

		return 0;
	}

	void Reader::waitForBufferToFill(comedi_t *dev, std::shared_ptr<std::vector<std::int64_t>> times)
	{
		for (int i = 1; i <= ANALOG_N; ++i)
		{
			/// TODO: Is this going to cause thread issues? Here we are just waiting for the buffer contents to be filled,
			/// correct? Fine if we can't think of any issues, just triggers my multithreading brain.
			// Wait for samples to be read to generate next timestamp
			while (comedi_get_buffer_contents(dev, ANALOG_READ_SUBDEV) < (N_CHANS * bytes_per_analog_sample) * i)
				;

			// Fill out timestamp for sampled values
			(*times)[i - 1] = getTimestamp();
		}
	}

	int Reader::readFromAnalogDevice(comedi_t *dev, char *buf, const int BUFSZ)
	{
		return read(comedi_fileno(dev), buf, BUFSZ);
	}

	void Reader::convertAndFillData(char *buf, std::shared_ptr<Matrix<float>> data)
	{
		for (size_t i = 0; i < N_CHANS; i++)
		{
			for (size_t j = 0; j < ANALOG_N; j++)
			{
				lsampl_t datum = ((lsampl_t *)buf)[j * N_CHANS + i];
				data->at(i, j) = convertDatum(datum, i);
			}
		}
	}

	void Reader::handleReadError(int ret)
	{
		if (ret < 0)
		{
			/* some error occurred */
			perror("read");
		}
		else if (ret == 0)
		{
			// unexpected
			assert(false);
		}
	}

	int Reader::readFromDigitalDevice()
	{
		comedi_t *d_device = digital_device->dev;

		unsigned int mask = 0;
		unsigned int bits = 0;
		int retval = comedi_dio_bitfield2(d_device, DIGITAL_READ_SUBDEV, mask, &bits, 0);
		if (retval < 0)
		{
			comedi_perror(DIGITAL_FILENAME);
		}

		return bits;
	}

};
