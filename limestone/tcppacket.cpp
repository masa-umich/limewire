/*
 * tcppacket.cpp
 *
 * Created on: March 16, 2024
 *      Author: jackmh
 */

#include "tcppacket.h"

// extern int process_telemetry_data(struct telemetry_data data);
// extern int process_acknowledgement(uint8_t ack_type);

// Takes packet directly from the FC and calls the appropriate function
// Also creates an acknolwedgement packet if needed
struct tcppacket tcppacket_decode(struct tcppacket *incoming_packet) {
    char* data = incoming_packet->packet;
    int data_len = incoming_packet->packet_len;
    int header = data[0];
    switch (header) {
        case 0x01: { // Telemetry Data Packet
            // First byte after the header is the amount of samples in the packet
            struct telemetry_data telem_data;
            uint8_t num_samples = data[1];
            telem_data.num_samples = num_samples;
            // For each sample we have, extract the 4 bytes of sample data and 8 bytes of time stamp data
            for (int i = 0; i < num_samples; i++) {
                uint32_t sample = (data[2 + i*12] << 24) | (data[3 + i*12] << 16) | (data[4 + i*12] << 8) | data[5 + i*12];
                uint64_t timestamp = (data[6 + i*12] << 56) | (data[7 + i*12] << 48) | (data[8 + i*12] << 40) | (data[9 + i*12] << 32) | (data[10 + i*12] << 24) | (data[11 + i*12] << 16) | (data[12 + i*12] << 8) | data[13 + i*12];
                // Append the sample and timestamp to the telemetry data struct
                telem_data.sample[i] = sample;
                telem_data.timestamp[i] = timestamp;
            }
            // process_telemetry_data(telem_data); // Replace with mutex later
            // Make acknowledgement packet
            struct tcppacket ack_packet;
            ack_packet.packet = new char[2];
            ack_packet.packet[0] = 0x0A;
            ack_packet.packet[1] = 0x01;
            ack_packet.packet_len = 2;
            return ack_packet;
            break;
            }
        case 0x0A: {
            // First byte after the header is the packet type the ack is for
            uint8_t ack_type = data[1];
            // process_acknowledgement(ack_type);
            // Acknowledgement packet
            break;
            }
        default: {
            // We don't need to handle any other packet types
            break;
            }
    }
}

// Takes a finite state machine transition and translates it into a command packet for the FC
struct tcppacket tcppacket_fsm_encode(int fsm_transition) {
    struct tcppacket fsm_packet;
    fsm_packet.packet = new char[2];
    fsm_packet.packet[0] = 0x02;
    fsm_packet.packet[1] = fsm_transition;
}

// Takes a valve command from Synnax and translates it into the bitmask packet for the FC 
struct tcppacket tcppacket_valve_encode(uint32_t valve, uint32_t state) {
    struct tcppacket valve_packet;
    valve_packet.packet = new char[9];
    valve_packet.packet[0] = 0x03;
    // Write the next 4 bytes as the valve selection bitmask
    valve_packet.packet[1] = (valve >> 24) & 0xFF;
    valve_packet.packet[2] = (valve >> 16) & 0xFF;
    valve_packet.packet[3] = (valve >> 8) & 0xFF;
    valve_packet.packet[4] = valve & 0xFF;
    // Write the next 4 bytes as the valve state bitmask
    valve_packet.packet[5] = (state >> 24) & 0xFF;
    valve_packet.packet[6] = (state >> 16) & 0xFF;
    valve_packet.packet[7] = (state >> 8) & 0xFF;
    valve_packet.packet[8] = state & 0xFF;
    // Set the packet length
    valve_packet.packet_len = 9;
    return valve_packet;
}

//  Takes calibration data from Synnax and translates it into a calibration packet for the FC
struct tcppacket tcppacket_calibrations_encode(uint64_t* calibration_data) {
    struct tcppacket cal_packet;
    cal_packet.packet = new char[33];
    cal_packet.packet[0] = 0x04;
    // TODO: this
}

// Prints the packet to the console
// Should only be used for debugging, safe to remove on final build
void tcppacket_print_packet(struct tcppacket packet) {
    for (int i = 0; i < packet.packet_len; i++) {
        // std::hex is used for printing in hex to the console
        // The static_cast<int> is used to convert the char to an int so it prints the number instead of the character
        std::cout << "0x" << std::hex << static_cast<int>(packet.packet[i]) << " ";
    }
    std::cout << std::endl;
}