
CXX ?= g++

CXXFLAGS ?= --std=c++17 -Wall -Werror 

%.exe: %.cpp reader.cpp writer.cpp comedi_device.cpp
	$(CXX) $(CXXFLAGS) $^ -o $@ -lcomedi -lm

test: analog_read_tests.exe
	./analog_read_tests.exe

clean:
	rm -rvf *.exe
