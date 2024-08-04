/*
 * tcppacket.h
 *
 * Created on: March 16, 2024
 *      Author: jackmh
 * 
 * Note: this is different than tcppacket.h and tcppacket.c from the fc drivers
 */
#include <string.h>

struct packet {
    char *packet;
    int packet_len;
};

#ifndef TCPPACKET_H_
#define TCPPACKET_H_

// Takes packet directly from the FC and calls the appropriate function
// Also creates an acknolwedgement packet if needed
struct packet tcppacket_decode(struct packet *incoming_packet);

// Takes a valve command from Synnax and translates it into the bitmask packet for the FC 
struct packet tcppacket_valve_encode(int command);

// Takes a finite state machine transition and translates it into a command packet for the FC
struct packet tcppacket_fsm_encode(int fsm_transition);

//  Takes calibration data from Synnax and translates it into a calibration packet for the FC
struct packet tcppacket_calibrations_encode(uint64_t* calibration_data);

#endif /* TCPPACKET_H_ */