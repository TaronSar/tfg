///    \file Mutex_spinlock.cpp
///
///    \date 27 ago. 2024
///
///    \author      Caio Iriarte, cis11 (at) embention.com
///    Company      Embention S.A.
///
///    Mutex_spinlock class implementation.
///


#include <Mutex_spinlock.h>

///  Extern methods used for lock/unlock (mutex)
extern "C" void spin_lock(Uint32* x);
extern "C" void spin_unlock(Uint32* x);


namespace Zusp
{

void Mutex::lock(Mutex_state* var_mutex)
{
    spin_lock(var_mutex);
}

void Mutex::unlock(Mutex_state* var_mutex)
{
    spin_unlock(var_mutex);
}

}