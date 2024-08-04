/*
 * tcpwriter.cpp
 *
 * Created on: March 16, 2024
 *      Author: jackmh
 * 
 * Note: must be using linux (or wsl) cuz socket.h
 * 
 * Outline:
 * 
 */

#include "tcpwriter.h"

namespace tcpwriter {
    tcpwriter::tcpwriter() {
        tcp_writer_init();
    }

    int tcpwriter::tcp_writer_init() {
        return 0;
    } 

    int tcpwriter::send_cmd_valve_control(uint32_t valve, uint32_t state) {
        // TODO: Take control of the connection mutex

        // Encode the valve command
        struct packet valve_packet = tcppacket_valve_encode(valve, state);
        // Send over the socket
        send();

        // TODO: Release the connection mutex 
        
    }

    int tcpwriter::send_cmd_fsm(int fsm_transition) {
        struct packet fsm_packet = tcppacket_fsm_encode(fsm_transition);
        // TODO: send this packet w/ <sys/socket.h>
        
        };
    }

    int tcpwriter::send_cmd_config_calibration(uint64_t* calibration_data) {
        // I wrote this as a uint64_t* but that's probably not how this should be, we should probably be sending more abstract slopes and offsets
        // TODO:
        // Convert the slopes and offsets to an array of uint64_t* to be written directly to the FC eeprom
    }

    int tcpwriter::tcp_writer_close_connection() {
        // TODO:
        // Close connection object
    }
}