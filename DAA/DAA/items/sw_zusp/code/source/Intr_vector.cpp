///    \file Intr_vector.cpp
///
///    \date 3 sep. 2024
///
///    \author      Victor Morales, vmm6 (at) embention.com
///    Company      Embention S.A.
///
///    Intr_vector implementation.
///


#include <Intr_vector.h>

// Default handlers for each exception
Zusp::Exception::Vec_table_entry Zusp::Intr_vector::excep_vec_table[exc_id_last + 1] =
{
	{null_handler, NULL},
	{sync_er_handler, NULL},
	{null_handler, NULL},
	{null_handler, NULL},
	{serror_handler, NULL},
};

/// Default handler.
/// \param[in] data        pointer to interrupt data.
/// \return none.
void Zusp::Intr_vector::null_handler(void* data)
{
	while(1) {
		;
	}
}

/// Syncronization error exception handler.
/// \param[in] data        pointer to interrupt data.
/// \return none.
void Zusp::Intr_vector::sync_er_handler(void* data)
{
    //Add debug message
	while(1) {
		;
	}
}

/// System error exception handler.
/// \param[in] data        pointer to interrupt data.
/// \return none.
void Zusp::Intr_vector::serror_handler(void* data)
{
        //Add debug message
	while(1) {
		;
	}
}

/// FIQs handler.
/// \return none.
void fiq_interrupt(void)
{
    Zusp::Intr_vector::excep_vec_table[exc_id_fiq_int].handler(Zusp::Intr_vector::excep_vec_table[exc_id_fiq_int].data);
}

/// IRQs handler.
/// \return none.
void irq_interrupt(void)
{
    Zusp::Intr_vector::excep_vec_table[exc_id_irq_int].handler(Zusp::Intr_vector::excep_vec_table[exc_id_irq_int].data);
}

/// Syncronization error interrupt handler.
/// \return none.
void sync_interrupt(void)
{
    Zusp::Intr_vector::excep_vec_table[exc_id_sync_int].handler(Zusp::Intr_vector::excep_vec_table[exc_id_sync_int].data);
}

/// System error interrupt handler.
/// \return none.
void serr_interrupt(void)
{
    Zusp::Intr_vector::excep_vec_table[exc_id_sea_int].handler(Zusp::Intr_vector::excep_vec_table[exc_id_sea_int].data);
}
