/*
 * tcpreader.cpp
 *
 * Created on: March 16, 2024
 *      Author: jackmh
 * 
 * Note: must be using linux (or wsl) cuz socket.h
 */

#include "tcpreader.h"

namespace tcpreader {
    tcpreader::tcpreader() {
        tcp_reader_init();
    }
    int tcpreader::tcp_reader_init() {
        // Creating socket file descriptor
        if ((server_fd = socket(AF_INET, SOCK_STREAM, 0)) == 0) {
            std::cerr << "Socket creation error" << std::endl;
            return -1;
        }

        address.sin_family = AF_INET;
        address.sin_addr.s_addr = INADDR_ANY;
        address.sin_port = htons(8080);

        // Binding socket to port
        if (bind(server_fd, (struct sockaddr *)&address, sizeof(address)) < 0) {
            std::cerr << "Bind failed" << std::endl;
            return -1;
        }
        return 0;
    }
    int tcpreader::tcp_reader_listen() {
        // Listening for connections
        if (listen(server_fd, 3) < 0) {
            std::cerr << "Listen failed" << std::endl;
            return -1;
        }
    
        // Accepting incoming connections
        if ((client_socket = accept(server_fd, (struct sockaddr *)&address, (socklen_t*)&addrlen)) < 0) {
            std::cerr << "Accept failed" << std::endl;
            return -1;
        }
    
        // Reading data from client and storing it into buffer
        valread = read(client_socket, buffer, BUFFER_SIZE);
        packet rxPacket;
        rxPacket.packet = buffer;
        rxPacket.packet_len = BUFFER_SIZE;
        if (valread < 0) {
            std::cerr << "Read error" << std::endl;
            return -1;
        }
    
        std::cout << "Received packet contents: " << buffer << std::endl;
        std::cout << "Parsing..." << std::endl;
        
        packet txPacket; // For the ack
        tcppacket_parse(rxPacket, txPacket);    
        // TODO:
        // Process data
        // Send it to synnax (might be best to do this in the h file or how ever it needs to be done)

        return 0;
    }

    int tcpreader::tcp_reader_close() {
        close(server_fd);
    }
}