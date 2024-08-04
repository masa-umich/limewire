%.exe: %.c
	gcc -o $@ $< -lcomedi -lm 

%.exe: %.cpp
	g++ -o $@ $< -lcomedi -lm -Werror -Wall 


clean:
	rm -f *.exe

plot:
	gnuplot --persist -e 'plot "test.out" u 1'
