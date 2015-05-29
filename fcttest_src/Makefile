# Build libdsm.a library.
#
# Based on examples from
# http://www.cs.colby.edu/maxwell/courses/tutorials/maketutor/

CC=gcc
CFLAGS=
#DEPS = #blah.h
OBJ = fcttest.o
BIN = fcttest

# Build as a STATIC library:

# Compile objects
%.o: %.c $(DEPS)
	$(CC) -c -o $@ $< $(CFLAGS)

# Make library, by archiving the objects.
$(BIN): $(OBJ)
	$(CC) -o $(BIN) $(OBJ) $(CFLAGS)

.PHONY: clean

clean:
	rm -f $(OBJ) $(BIN)

