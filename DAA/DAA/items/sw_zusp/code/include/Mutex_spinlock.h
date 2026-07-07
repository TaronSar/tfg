///    \file Mutex_spinlock.h
///
///    \date 27 ago. 2024
///
///    \author      Caio Iriarte, cis11 (at) embention.com
///    Company      Embention S.A.
///
///    Mutex_spinlock class declaration.
///


#ifndef ZUSP_MUTEX_H_
#define ZUSP_MUTEX_H_

#include <Entypes.h>

namespace Zusp
{

/// Mutex variable type (encapsulation)
typedef Uint32 Mutex_state;

class Mutex
{
    public:
        /// The calling thread locks the mutex, blocking if necessary
        static void lock(Mutex_state* var_mutex);

        /// Unlocks the mutex, releasing ownership over it.
        /// If the mutex is not currently locked by the calling thread,
        /// it causes undefined behavior.
        static void unlock(Mutex_state* var_mutex);
};

}

#endif