/*
 * tcpwriter.h
 *
 * Created on: March 16, 2024
 *      Author: jackmh
 * 
 * Note: must be using linux (or wsl) cuz socket.h
 */

#include <sys/socket.h> // Linux TCP API
#include "tcppacket.h" // Packet parsing
#include <iostream>
#include <netinet/in.h>
#include <unistd.h>
#include <cstring>

#ifndef TCPWRITER_H_
#define TCPWRITER_H_

namespace tcpwriter {
    class tcpwriter {
        public:
            // Basically just calls init
            tcpwriter();
            
            // Binds to a server (fc)
            virtual int tcp_writer_init();
            // Send the command for a finite state machine transition
            virtual int send_cmd_fsm(int fsm_transition);
            // Send the command to toggle on or off selected valves
            virtual int send_cmd_valve_control(uint32_t valve, uint32_t state);
            // Send the command to update the onboard configuration file
            virtual int send_cmd_config_calibration(uint64_t* calibration_data);
            // If there is an open connection to the flight computer, close it
            virtual int tcp_writer_close_connection();
        private:
            // Nothing atm
            // Probably a connection object
    };
}

#endif /* TCPWRITER */