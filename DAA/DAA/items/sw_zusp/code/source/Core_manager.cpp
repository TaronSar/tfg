///    \file Core_manager.cpp
///
///    \date 3 sep. 2024
///
///    \author      Victor Morales, vmm6 (at) embention.com
///    Company      Embention S.A.
///
///    Core_manager class implementation.
///


#include <Core_manager.h>
#include <Core_utils.h>

namespace Zusp
{
	/// Constructor.
	/// \param[in] core_id          core id.
	/// \param[in] start_point      Handler where the core execution starts.
	/// \param[in] data             Support data.
	/// \return none.
	Core_manager::Core_manager(Uint8 core_id, Irq_manager::Handler_ptr start_point, void* data) : id(core_id)
	{
		/// \alg
		/// <ul>
		/// <li> Set handler and status to false
		core_handler.handler = start_point;
		core_handler.data = data;
		status = false;
		/// </ul>
	}

	/// Start up the core execution.
	/// \return error code.
	Uint8 Core_manager::run()
	{
		/// \alg
		/// <ul>
		Uint8 core_mask;
		Uint8 ret = 0;
		/// <li> Get self core id and target core.
		Uint8 core_id = Core_utils::get_id();
		Uint8 target_id = get_id();
		/// <li> Check if core running this method is the master core.
		if(core_id == master_core_id)
		{
			/// <ul>
			/// <li> Create IRQ for the desired core with the specified handler.
			core_mask = 1 << target_id;
			Zusp::Irq_manager irq_core(init_core_irq, core_mask, core_handler);
			/// <li> Singal the IRQ.
			Uint8 dbg_error = irq_core.signal();
			status = true;
			/// </ul>
		}
		else
		{
			ret = 1;
		}
		/// <li> Return error code
		return 0;
		/// </ul>
	}

	/// Core status getter.
	/// \return core status.
	bool Core_manager::get_status()
	{
		/// \alg
		/// <ul>
		/// <li> Return core status
		return status;
		/// </ul>
	}
    
	/// Core id getter.
	/// \return core id.
	Uint8 Core_manager::get_id()
	{
		/// \alg
		/// <ul>
		/// <li> Return core id
		return id;
		/// </ul>
	}

}