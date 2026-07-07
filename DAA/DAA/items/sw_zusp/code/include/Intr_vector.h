///    \file Intr_vector.h
///
///    \date 3 sep. 2024
///
///    \author      Victor Morales, vmm6 (at) embention.com
///    Company      Embention S.A.
///
///    Intr_vector header.
///

#ifndef ZUSP_INTERRUPT_VECTOR_H_
#define ZUSP_INTERRUPT_VECTOR_H_

#include <Exception.h>


/// FIQs handler.
/// \return none.
void fiq_interrupt(void);

/// IRQs handler.
/// \return none.
void irq_interrupt(void);

/// Syncronization error interrupt handler.
/// \return none.
void sync_interrupt(void);

/// System error interrupt handler.
/// \return none.
void serr_interrupt(void);

namespace Zusp
{

    class Intr_vector
    {
        public:
            /// Array with exceptions
            static Exception::Vec_table_entry excep_vec_table[];

        private:

            /// Default handler.
            /// \param[in] data        pointer to interrupt data.
            /// \return none.
            static void null_handler(void* data);

            /// Syncronization error exception handler.
            /// \param[in] data        pointer to interrupt data.
            /// \return none.
            static void sync_er_handler(void* data);

            /// System error exception handler.
            /// \param[in] data        pointer to interrupt data.
            /// \return none.
            static void serror_handler(void* data);

    };


}


#endif // ZUSP_INTERRUPT_VECTOR_H_