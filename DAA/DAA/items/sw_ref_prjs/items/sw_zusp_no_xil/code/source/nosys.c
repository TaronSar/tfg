

#include <sys/types.h>

caddr_t _sbrk ( int incr )
{
    return 0;
}

int _kill(pid_t pid, int sig)
{
    return 0;
}


int _getpid(void)
{
    return 0;
}

size_t _write(int handle, const char * buffer, size_t size)
{
    return 0;
}


int _close(int fd)
{
    return 0;
}


int _fstat(int fd, struct stat *buf)
{
    return 0;
}


int _isatty(int fd)
{
    return 0;
}


int _lseek(int fd, off_t offset, int whence)
{
    return 0;
}


size_t _read(int handle, char * buffer, size_t size)
{
    return 0;
}