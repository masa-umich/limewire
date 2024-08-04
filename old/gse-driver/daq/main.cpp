#include"reader.h"
#include"writer.h"

#include<memory>
#include<iostream>
#include"matrix.h"

#include<unistd.h>

void testAnalogBasic();
void testDigitalInputBasic();
void testDigitalOutputBasic();
void testReaderReads();
void testAnalogDigital();
void testTCs();
void testGhosting();

int main()
{
	std::cout << "Which test to run?\n 1) Analog Basic\n 2) DO Basic\n 3) DI Basic\n 4) Reader Reads\n 5) Analog/Digital\n 6) TCs\n 7) Ghosting" << std::endl;
	int input = 0;
	std::cin >> input;

	switch (input) {
		case 1:
			testAnalogBasic();
			break;
		case 2:
			testDigitalOutputBasic();
			break;
		case 3:
			testDigitalInputBasic();
			break;
		case 4: 
			testReaderReads();
			break;
		case 5:
			testAnalogDigital();
			break;
		case 6:
			testTCs();
			break;
		case 7:
			testGhosting();
			break;
		default:
			std::cout << "Invalid input" << std::endl;
			exit(1);
	}
	
	exit(0);	
}

#define SLOPE (float)17.193

void testAnalogBasic() {
	auto data = std::make_shared<Matrix<float>>(N_CHANS, ANALOG_N);
	auto times = std::make_shared<std::vector<std::int64_t>>(ANALOG_N);
	
	DAQ::Reader* reader = new DAQ::Reader();

	reader->start(); // Start reading

	for (;;) {
	
		reader->readAnalog(data, times);

		for (int i = 0; i < 11; ++i) {
			//if (i == 4 || i == 6) continue;
			std::cout << "PT " << i+1 << ": " << (*data).at(i,0) << std::endl;
		}

		//for (int i = 0; i < 24; ++i) {
		//	std::cout << "data " << (*data).at(0, i) << std::endl; // PT channel 0 @ time i
		//}

	/*	std::cout << "data TC 1 " << (*data).at(64, 0) << std::endl;
		std::cout << "data TC 2 " << (*data).at(65, 0) << std::endl;
		std::cout << "data TC 4 raw " << (*data).at(67, 0) << std::endl;
		std::cout << "data TC 4 conv " << 1.114 - ((*data).at(67, 0) / 2)<< std::endl;
*/		std::cout << "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~" << std::endl;

		std::cout << "PT 37" << ": " << (*data).at(60, 0) << std::endl; // PT channel 37 @ time 0

		std::this_thread::sleep_for(std::chrono::milliseconds(1000));
	
	}

	reader->stop(); // Stop reading

	delete reader;
}

void testGhosting() {
	auto data = std::make_shared<Matrix<float>>(N_CHANS, ANALOG_N);
	auto times = std::make_shared<std::vector<std::int64_t>>(ANALOG_N);
	
	DAQ::Reader* reader = new DAQ::Reader();

	reader->start(); // Start reading

	for (;;) {
	
		reader->readAnalog(data, times);

		std::cout << "data PT 1 " << (*data).at(0, 0) << std::endl;
		std::cout << "data PT 2 " << (*data).at(1, 0) << std::endl;
		std::cout << "data PT 3 " << (*data).at(2, 0) << std::endl;
		std::cout << "data PT 4 " << (*data).at(3, 0) << std::endl;
		std::cout << "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~" << std::endl;

		std::this_thread::sleep_for(std::chrono::milliseconds(500));
	
	}

	reader->stop(); // Stop reading

	delete reader;
}

void testDigitalInputBasic() {
	auto data = std::make_shared<std::vector<std::uint32_t>>(1);
	auto times = std::make_shared<std::vector<std::int64_t>>(1);
	
	DAQ::Reader* reader = new DAQ::Reader();

	reader->start(); // Start reading

	for (int i = 0; i < 5; ++i) {

		reader->readDigital(data, times);
		
		std::cout << "data " << std::hex << (*data).at(0) << std::endl; // DI channel 0 @ time i

		sleep(1);
	
	}

	reader->stop(); // Stop reading

	delete reader;
}

void testReaderReads() {
	auto d_data = std::make_shared<std::vector<std::uint32_t>>(1);
	auto d_times = std::make_shared<std::vector<std::int64_t>>(1);
	auto a_data = std::make_shared<Matrix<float>>(N_CHANS, ANALOG_N);
	auto a_times = std::make_shared<std::vector<std::int64_t>>(ANALOG_N);
	
	DAQ::Reader* reader = new DAQ::Reader();

	reader->start(); // Start reading

	for (int i = 0; i < 5; ++i) {

		reader->readDigital(d_data, d_times);
		reader->readAnalog(a_data, a_times);
		
		std::cout << "digital data " << std::hex << (*d_data).at(0) << " @ time " << (*d_times).at(0) << std::endl; // DI channel 0 @ time 0
		std::cout << "analog data " << (*a_data).at(0,i) << " @ time " << (*a_times).at(1) << std::endl; // PT channel 0 @ time 1
		std::cout << "analog data " << (*a_data).at(1,i) << " @ time " << (*a_times).at(1) << std::endl; // PT channel 0 @ time 1
		std::cout << "analog data " << (*a_data).at(2,i) << " @ time " << (*a_times).at(1) << std::endl; // PT channel 0 @ time 1
		std::cout << "analog data " << (*a_data).at(3,i) << " @ time " << (*a_times).at(1) << std::endl; // PT channel 0 @ time 1
		std::cout << "analog data " << (*a_data).at(4,i) << " @ time " << (*a_times).at(1) << std::endl; // PT channel 0 @ time 1

		for (int j = 0; j < ANALOG_N; ++j) {
			for (int k = 0; k < ANALOG_N; ++k) {
				//std::cout << j << " analog data PT" << k << " " << (*a_data).at(k,j) << std::endl;
				if ((*a_data).at(k,j) == 0 || (*a_data).at(k,j) > 1.5 || (*a_data).at(k,j) < -1.5) {
					std::cout << j << " analog data PT" << k << " " << (*a_data).at(k,j) << std::endl;
					exit(-1);
				}
			}
		}

		sleep(1);
	
	}

	reader->stop(); // Stop reading

	delete reader;
}

void testDigitalOutputBasic() {
// Turn on channels 1 by 1, print enable state each time, then all off
	DAQ::Writer* writer = new DAQ::Writer();

	uint32_t retVal = 0;

	for (uint32_t i = 0; i < 24; i += 1) {

		retVal = writer->writeDigital((1 << i), 0xFFFFFFFF); // Channel i on

		printf("0x%08x \n", retVal);

		sleep(1);

	}

	retVal = writer->writeDigital(0xFFFFFFFF, 0x0); // Channels all off

	printf("0x%08x \n", retVal);

	delete writer;
}

void testAnalogDigital() {
auto data = std::make_shared<Matrix<float>>(N_CHANS, ANALOG_N);
	auto times = std::make_shared<std::vector<std::int64_t>>(ANALOG_N);
	
	DAQ::Reader* reader = new DAQ::Reader();

	DAQ::Writer* writer = new DAQ::Writer();

	uint32_t retVal = 0;

	reader->start(); // Start reading

	retVal = writer->writeDigital(0x1, 0x1); // Turn valve channel 1 on
	printf("0x%08x \n", retVal);

	reader->readAnalog(data, times);
	
	for (int i = 0; i < ANALOG_N; ++i) {
		std::cout << "data " << (*data).at(36, i) << std::endl; // CURR for valve channel 1 @ time i
	}

	sleep(1);
	for (int i = 0; i < ANALOG_N; ++i) {
		std::cout << "data " << (*data).at(36, i) << std::endl; // CURR for valve channel 1 @ time i
	}

	sleep(1);

	retVal = writer->writeDigital(0x1, 0x0); // Turn valve channel 1 off
	printf("0x%08x \n", retVal);

	reader->readAnalog(data, times);

	for (int i = 0; i < ANALOG_N; ++i) {
		std::cout << "data " << (*data).at(36, i) << std::endl; // CURR for valve channel 1 @ time i
	}

	reader->stop(); // Stop reading

	delete reader;
	delete writer;
}

void testTCs() {

	auto data = std::make_shared<Matrix<float>>(N_CHANS, ANALOG_N);
	auto times = std::make_shared<std::vector<std::int64_t>>(ANALOG_N);

	DAQ::Reader* reader = new DAQ::Reader();

	reader->start(); // Start reading

	for (;;) {

		reader->readAnalog(data, times);

		const int FIRST_TC = 64;

		for (int i = FIRST_TC; i < FIRST_TC + 16; ++i) {
			std::cout << "TC " << i-FIRST_TC+1 << ": " << (*data).at(i, 0) << std::endl; // TC channel i @ time 0
		}

		std::cout << "~~~~~~~~~~~~~~~~~~~~~~" << std::endl;

		std::this_thread::sleep_for(std::chrono::milliseconds(500));

	}

	reader->stop(); // Stop reading

	delete reader;
}
