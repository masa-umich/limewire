
#include <stdio.h>		/* for printf() */
#include <stdlib.h>
#include <comedilib.h>
#include <ctype.h>
#include <math.h>

int read_subdev = 0;			/* change this to your input subdevice */
int write_subdev = 1;
const char filename[] = "/dev/comedi0";

int main(int argc, char *argv[])
{
	comedi_t *device;
	int retval;
	unsigned int bits = 0;
	unsigned int * bits_ptr = &bits; 
	unsigned int write_mask;
	
	device = comedi_open(filename);

	int n_scan = 1000;

	for (int i = 0; i < n_scan; i++){

		write_mask = 0;
		if (device == NULL) {
			comedi_perror(filename);
			return 1;
		}
		
		retval = comedi_dio_bitfield2(device, read_subdev, write_mask, bits_ptr, 0);
		printf("%d\n", bits);

		if (retval < 0) {
			comedi_perror(filename);
			return 1;
		}

		write_mask = 4294967295;
		retval = comedi_dio_bitfield2(device, write_subdev, write_mask, bits_ptr, 0);

		if (retval < 0) {
			comedi_perror(filename);
			return 1;
		}
	}	
	return 0;
}

