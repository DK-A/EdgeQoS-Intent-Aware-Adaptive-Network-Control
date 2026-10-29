CC ?= gcc
CFLAGS ?= -O2 -Wall -Wextra

all: nflog_reader

nflog_reader: nflog_reader.c
	$(CC) $(CFLAGS) -o nflog_reader nflog_reader.c

clean:
	rm -f nflog_reader

.PHONY: all clean
