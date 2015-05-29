/*
  fcctest

  Test the flow completion time. Server and client must each be started
  with the size of the flow specified. The client and server first establish
  a connection, then the client marks the start time, and sends a flow
  of the specified size. The server, once receiving the specified number
  of bytes, sends back a single-byte token. Upon receiving the token,
  the client marks the end time. The flow completing time reported is
  the difference between this start and end time.

  Can enable RC3 mode if needed using the -r option, but it must be
  enabled for both the client and server.
*/
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <getopt.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <stdbool.h>
#include <time.h>

#define vprintf(...)  {if(verbose) printf(__VA_ARGS__);}

static void do_server(uint16_t port);
static void do_client(const char *addr, uint16_t port);
static void set_rc3_options(int sock_fd);

bool verbose = false;

bool rc3 = false;
bool rc3_log = false;
bool rc3_logtime = false;

int length = 0;

void usage()
{
  printf(
    "fcttest - A flow-completion-time measurement tool.\n"
    "Options:\n"
    "  -s    Sever mode (either -s or -c must be specified).\n"
    "\n"
    "  -c    Client mode (either -s or -c must be specified).\n"
    "\n"
    "  -p    Port to listen on (server mode) or connect to (client mode).\n"
    "\n"
    "  -a address    Address of server (must be specified in client mode).\n"
    "\n"
    "  -g flow_len    Length, in bytes, of flow. Must be specified on\n"
    "                 both the server and client.\n"
    "\n"
    "  -r    Enable RC3 mode. Must be specified for both client and server,\n"
    "        or neither.\n"
    "\n"
    "  -l    Enable RC3 logging mode (kernel socket option).\n"
    "\n"
    "  -t    Enable RC3 logging time mode (kernel socket option).\n"
    "\n"
    "  -v    Verbose mode. Only recommended for troubleshooting, can\n"
    "        increase the measured times, due to extra printing.\n"
  );
}


int main(int argc, char *argv[])
{
  int opt;
  bool server = false;
  bool client = false;
  uint16_t port = 0;
  char *address = 0;

  while ((opt = getopt(argc, argv, "sca:p:g:rltv")) != -1) {
    switch (opt) {
    case 's':
      vprintf("server mode\n");
      server = true;
      break;
    case 'c':
      vprintf("client mode\n");
      client = true;
      break;
    case 'p':
      port = atoi(optarg);
      vprintf("port = %d\n", port);
      break;
    case 'a':
      vprintf("address = %s\n", optarg);
      address = malloc(strlen(optarg)+1);
      strcpy(address, optarg);
      break;
    case 'g':
      length = atoi(optarg);
      vprintf("length = %d\n", length);
      break;
    case 'r':
      vprintf("RC3 mode on!\n");
      rc3 = true;
      break;
    case 'l':
      vprintf("RC3 logging mode on!\n");
      rc3_log = true;
      break;
    case 't':
      vprintf("RC3 logging time mode on!\n");
      rc3_logtime = true;
      break;
    case 'v':
      verbose = true;
      vprintf("Verbose mode on!. Timing is now less accurate.\n");
      break;
    default:
      usage();
      exit(EXIT_FAILURE);
    }
  }

  if (server && client) {
    fprintf(stderr, "[ERROR] Can't be server AND client.");
    printf("\n");
    usage();
    exit(EXIT_FAILURE);
  }

  if (!port) {
    fprintf(stderr, "[ERROR] Must set a port.");
    printf("\n");
    usage();
    exit(EXIT_FAILURE);
  }

  if (!length) {
    fprintf(stderr, "[ERROR] Need length!\n");
    printf("\n");
    usage();
    exit(EXIT_FAILURE);
  }

  if (server) {
    do_server(port);
    exit(0);
  }
  if (client) {
    do_client(address, port);
    exit(0);
  }

  fprintf(stderr, "[ERROR] must be client or server.\n");
  printf("\n");
  usage();
}

static void do_server(uint16_t port)
{
  int serv_fd;
  int client_fd;
  struct sockaddr_in serv_addr, client_addr;

  serv_fd = socket(AF_INET, SOCK_STREAM, 0);
  if (serv_fd == -1) {
    fprintf(stderr, "[ERROR] couldn't make socket.\n");
    exit(EXIT_FAILURE);
  }

  // Allow re-use of the port without dumb bind error.
  int one = 1;
  setsockopt(serv_fd, SOL_SOCKET, SO_REUSEPORT, &one, sizeof(one));

  set_rc3_options(serv_fd);

  // Setup address for bind to listen on any addres, and specific port
  memset(&serv_addr, 0, sizeof(serv_addr));
  serv_addr.sin_family = AF_INET;
  serv_addr.sin_addr.s_addr = INADDR_ANY;
  serv_addr.sin_port = port;

  if (-1 == bind(serv_fd, (struct sockaddr *)&serv_addr, sizeof(serv_addr))) {
    fprintf(stderr, "[ERROR] couldn't bind.\n");
    exit(EXIT_FAILURE);
  }

  if (-1 == listen(serv_fd, 1024)) {
    fprintf(stderr, "[ERROR] couldn't bind.\n");
    exit(EXIT_FAILURE);
  }

  // Setup a buffer to receive in.
  char *buffer = malloc(length);

  // Repeatedly do fct tests as clients request them (one at a time).
  while (1) {
    socklen_t slen = sizeof(client_addr);
    client_fd = accept(serv_fd, (struct sockaddr *)&client_addr, &slen);
    if (client_fd == -1) {
      fprintf(stderr, "[ERROR] couldn't bind.\n");
      exit(EXIT_FAILURE);
    }

    vprintf("Got connection!\n");

    set_rc3_options(client_fd);

    // Read data loop.
    int total = 0;
    int got = 0;
    while(total < length) {
      got = read(client_fd, &buffer[total], length - total);
      if (got <= 0) {
        fprintf(stderr, "[ERROR] got a bad amount of bytes %d\n", got);
        exit(EXIT_FAILURE);
      }
      vprintf("Got %d bytes\n", got);
      total += got;
    }

    vprintf("Writing response token\n");

    // Send the response token, siginalling to the client that I have
    // received the whole flow.
    char response_token = '$';
    write(client_fd, &response_token, 1);

    vprintf("Write token.\n");

    // Useful for debugging:
    // buffer[length-1]= '\0';
    // vprintf("Transfered string: \"%s\" \n", buffer);

    close(client_fd);

    vprintf("Connection closed.\n");
  }
}

static void do_client(const char *addr, uint16_t port)
{
  int fd;
  struct sockaddr_in serv_addr, client_addr;

  fd = socket(AF_INET, SOCK_STREAM, 0);
  if (fd == -1) {
    fprintf(stderr, "[ERROR] couldn't make socket.\n");
    exit(EXIT_FAILURE);
  }

  set_rc3_options(fd);

  memset(&serv_addr, 0, sizeof(serv_addr));
  serv_addr.sin_family = AF_INET;
  inet_aton(addr, &serv_addr.sin_addr);
  //serv_addr.sin_addr.s_addr =
  serv_addr.sin_port = port;

  if (connect(fd, (struct sockaddr *)&serv_addr, sizeof(serv_addr))) {
    fprintf(stderr, "[ERROR] couldn't connect.\n");
    exit(EXIT_FAILURE);
  }

  char *buff = malloc(length);

  struct timespec time_start, time_finish;

  clock_gettime(CLOCK_MONOTONIC, &time_start);

  write(fd, buff, length);

  vprintf("Sent via write syscall! Waiting for $ token.\n");

  int got;
  got = read(fd, buff, 1);

  vprintf("Got a byte.\n");

  clock_gettime(CLOCK_MONOTONIC, &time_finish);

  if (got != 1 || buff[0] != '$') {
    fprintf(stderr, "[ERROR] read %d bytes, first is %c\n", got, *buff);
    exit(EXIT_FAILURE);
  }

  uint64_t nanodiff
       = time_finish.tv_nsec + time_finish.tv_sec * (1000*1000*1000)
       - (time_start.tv_nsec + time_start.tv_sec * (1000*1000*1000));
  int secs = nanodiff / (1000*1000*1000);
  long nsecs = nanodiff % (1000*1000*1000);

  double f_msecs = nanodiff / (1000.0 * 1000.0);

  if (verbose) {
    printf("Time difference: %d secs, %ld nsecs\n", secs, nsecs);
    printf("Time difference: %f msecs\n", f_msecs);
  }
  else {
    printf("%f\n", f_msecs);
  }
}


static void set_rc3_options(int sock_fd)
{
  #define SO_RC3 60
  #define SO_LOGME 61
  #define SO_LOGTIME 62
  int val = 1;
  if(rc3) {
    vprintf("Enabling rc3.\n");
    if(setsockopt(sock_fd, SOL_SOCKET, SO_RC3, &val, sizeof(val))) {
      fprintf(stderr, "[ERROR] setting up RC3.");
      exit(EXIT_FAILURE);
    }
  }

  if(rc3_log) {
    vprintf("Enabling rc3 logging.\n");
    if(setsockopt(sock_fd, SOL_SOCKET, SO_LOGME, &val, sizeof(val))) {
      fprintf(stderr, "[ERROR] setting up RC3 logging.");
      exit(EXIT_FAILURE);
    }
  }

  if(rc3_logtime) {
    vprintf("Enabling rc3 logging time.\n");
    if(setsockopt(sock_fd, SOL_SOCKET, SO_LOGTIME, &val, sizeof(val))) {
      fprintf(stderr, "[ERROR] setting up RC3 logging time.");
      exit(EXIT_FAILURE);
    }
  }
}

