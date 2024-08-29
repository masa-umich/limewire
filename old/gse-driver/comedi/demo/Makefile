%.exe: %.c
	gcc -o $@ common.c $< -lcomedi -lm 

clean:
	rm -f *.exe

plot:
	gnuplot --persist -e 'plot "test.out" u 1'
