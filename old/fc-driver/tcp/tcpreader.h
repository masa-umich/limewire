/*
 * tcpreader.h
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

#ifndef TCPREADER_H_
#define TCPREADER_H_

const int BUFFER_SIZE = 1024; // this must be changed in the future, 1024 is way too low (should be dynamic)

namespace tcpreader {
    class tcpreader {
        public:
            tcpreader();

            // Trys to bind to the FC (creates a connection)
            virtual int tcp_reader_init();
            // Listens for incoming packets
            virtual int tcp_reader_listen();
            // Closes the active connection
            virtual int tcp_reader_close();
            // ...
            // async type telemetry readings and stuff idk how to do yet
        private:
            int server_fd, client_socket, valread;
            struct sockaddr_in address;
            int addrlen = sizeof(address);
            char buffer[BUFFER_SIZE] = {0};
    };
}

#endif /* TCPREADER_H_ */