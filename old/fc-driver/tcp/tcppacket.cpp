/*
 * tcppacket.cpp
 *
 * Created on: March 16, 2024
 *      Author: jackmh
 */

#include "tcppacket.h"

// Takes packet directly from the FC and calls the appropriate function
// Also creates an acknolwedgement packet if needed
struct packet tcppacket_decode(struct packet *incoming_packet) {

};

// Takes a valve command from Synnax and translates it into the bitmask packet for the FC 
struct packet tcppacket_valve_encode(uint32_t valve, uint32_t state) {

};

// Takes a finite state machine transition and translates it into a command packet for the FC
struct packet tcppacket_fsm_encode(int fsm_transition) {

};

//  Takes calibration data from Synnax and translates it into a calibration packet for the FC
struct packet tcppacket_calibrations_encode(uint64_t* calibration_data) {

};