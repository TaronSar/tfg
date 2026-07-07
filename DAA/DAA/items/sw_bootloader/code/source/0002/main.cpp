extern "C"
{
#include <platform.h>
}

#include <cstdio>

int main()
{
    init_platform();

    printf("Main 0002\n\r");

    cleanup_platform();

    return 0;
}
