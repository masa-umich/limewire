
#include <stdlib.h>
#include "gse-driver/comedi/comedilib.h"
#include <ctype.h>
#include <math.h>

#include <boost/asio.hpp>
#include <boost/bind/bind.hpp>

void getDigitalCB (const boost::system::error_code& /*e*/, boost::asio::steady_timer* t, comedi_t* device);
