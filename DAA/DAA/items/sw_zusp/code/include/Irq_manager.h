///    \file Irq_manager.h
///
///    \date 3 sep. 2024
///
///    \author      Victor Morales, vmm6 (at) embention.com
///    Company      Embention S.A.
///
///    Irq_manager class header.
///

#ifndef ZUSP_IRQ_MANAGER_H_
#define ZUSP_IRQ_MANAGER_H_

#include <Intr_vector.h>

namespace Zusp
{

    class Irq_manager
    {

        public:
            /// Pointer to handler
            typedef void (*Handler_ptr)(void* data);

            /// Interrupt handler
            typedef struct
            {
                Handler_ptr handler;    /// Pointer to handler for the interrupt
                void* data;             /// Pointer to interrupt data
            }
            Irq_handler;

            /// Interrupts groups
            typedef enum
            {
                secure,     /// group0 secure
                nonsecure,  /// group1 non secure  
            } 
            Security;

            /// Interrupt manager initialization.
            /// \return error code.
            static Uint8 init();

            /// Check interrupt manager initialization .
            /// \return interrupt manager initialization status.
            static bool check_init();

            /// Constructor.
            /// \param[in] id             interrupt id.
            /// \param[in] group        security group.
            /// \param[in] targets        core target mask.
            /// \param[in] handler        interrupt handler.
            /// \return none.
            Irq_manager(Uint16 id, Security group, Uint8 targets, Irq_handler handler);

            /// Constructor with secure group as default.
            /// \param[in] id             interrupt id.
            /// \param[in] targets        core target mask.
            /// \param[in] handler        interrupt handler.
            /// \return none.
            Irq_manager(Uint16 id, Uint8 targets, Irq_handler handler);

            /// Set interrupt handler.
            /// \param[in] handler        interrupt handler.
            /// \return error code.
            Uint8 set_handler(Irq_handler handler);

            /// Add specific core to the targets.
            /// \param[in] target        core id.
            /// \return error code.
            Uint8 add_target(Uint8 target);

            /// Remove specific core from the targets.
            /// \param[in] target        core id.
            /// \return error code.
            Uint8 remove_target(Uint8 target);

            /// Set core targets (each bit is a core).
            /// \param[in] targets        core target mask.
            /// \return error code.
            Uint8 set_targets(Uint8 targets);

            /// Security group setter.
            /// \param[in] grp        security group.
            /// \return error code.
            Uint8 set_security(Security grp);

            /// Current security group getter.
            /// \return security group.
            Security get_security();

            /// Interrupt id getter.
            /// \return interrupt id.
            Uint16 get_id();

            /// Trigger interrupt.
            /// \return error code.
            Uint8 signal();

            /// Interrupt enabler
            /// \return error code.
            Uint8 enable();

            /// Interrupt disabler.
            /// \return error code.
            Uint8 disable();

            /// Enablement getter.
            /// \return enable or not.
            bool get_status();

        private:

            // Array with the interrupts handlers
            static Irq_manager::Irq_handler irq_handlers[];
            
            // Status of the interrupts handlers (set or not sets) 
            static bool irq_hndl_set[];
            
            // Status of the manager (distributor, handlers, ...)
            static bool initialized;
            
            // Interrupt id
            Uint16 id;
            
            // Security group
            Security group;
            
            // Core targets to be signaled by the interrupt
            Uint8   core_targets;
            
            // Status of the interrupt
            bool enabled;
            
            // Default constructor deleted
            Irq_manager(); 
            
            
            /// Generic handler for IRQs.
            /// \param[in] irq_id        ID of interrupt to be handled.
            /// \return none.
            static void exc_irq_handler(Uint16 irq_id);

    };


}


#endif // ZUSP_IRQ_MANAGER_H_