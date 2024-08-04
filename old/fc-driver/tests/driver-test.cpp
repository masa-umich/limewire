#include "../tcp/tcpreader.h"
#include "../tcp/tcpwriter.h"

int main() {
    tcpwriter::tcpwriter *fc_writer = new tcpwriter::tcpwriter(); // Make the objects for the classes
    tcpreader::tcpreader *fc_reader = new tcpreader::tcpreader();
    
    //do commands
    //grab telemetry
    //yay

    delete fc_reader; // BYE BYE 🤫🧏
    delete fc_writer;
}