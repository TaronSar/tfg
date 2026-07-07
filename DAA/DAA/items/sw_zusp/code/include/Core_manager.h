///    \file Core_manager.h
///
///    \date 3 sep. 2024
///
///    \author      Victor Morales, vmm6 (at) embention.com
///    Company      Embention S.A.
///
///    Core_manager class header.
///


#ifndef ZUSP_CORE_MANAGER_H_
#define ZUSP_CORE_MANAGER_H_

#include <Irq_manager.h>

namespace Zusp
{

    class Core_manager
    {

        public:
            /// Constructor.
            /// \param[in] core_id          core id.
            /// \param[in] start_point      Handler where the core execution starts.
            /// \param[in] data             Support data.
            /// \return none.
            Core_manager(Uint8 core_id, Irq_manager::Handler_ptr start_point, void* data);

            /// Start up the core execution.
            /// \return error code.
            Uint8 run();

            /// Core status getter.
            /// \return core status.
            bool get_status();

            /// Core id getter.
            /// \return core id.
            Uint8 get_id();

        private:

            // Core id
            Uint8 id;

            // Core status
            bool status;
            
            // Interrupt handler for the core
            Irq_manager::Irq_handler core_handler;
            
            /// Default constructor removed.
            /// \return none.
            Core_manager();


    };


}


#endif // ZUSP_CORE_MANAGER_H_