#include <Printf.h>
extern "C"{
    #include <platform.h>
}

int main()
{
    
    init_platform();
    
    Zusp::Mutex mu(0);
    int n = 3;

    mu.lock();
    n = 5;
    mu.unlock();

    cleanup_platform();
    return 0;
}
