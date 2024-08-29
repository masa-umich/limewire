/*
 * tcppacket.h
 *
 * Created on: March 16, 2024
 *      Author: jackmh
 * 
 * Note: this is different than tcppacket.h and tcppacket.c from the fc drivers
 */
#ifndef TCPPACKET_H_
#define TCPPACKET_H_

#include <string.h>
#include <iostream>
#include <cstdint>

struct tcppacket {
    char *packet;
    int packet_len;
};

struct telemetry_data {
    uint8_t num_samples;
    uint32_t* sample;
    uint64_t* timestamp;
};

// Takes packet directly from the FC and calls the appropriate function
// Also creates an acknolwedgement packet if needed
struct tcppacket tcppacket_decode(struct tcppacket *incoming_packet);

// Takes a finite state machine transition and translates it into a command packet for the FC
struct tcppacket tcppacket_fsm_encode(int fsm_transition);

// Takes a valve command from Synnax and translates it into the bitmask packet for the FC 
struct tcppacket tcppacket_valve_encode(uint32_t valve, uint32_t state);

//  Takes calibration data from Synnax and translates it into a calibration packet for the FC
struct tcppacket tcppacket_calibrations_encode(uint64_t* calibration_data);

// Prints the packet to the console
// Should only be used for debugging, safe to remove on final build
void tcppacket_print_packet(struct tcppacket packet);

#endif /* TCPPACKET_H_ */