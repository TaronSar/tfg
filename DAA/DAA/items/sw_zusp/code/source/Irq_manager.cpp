///    \file Irq_manager.h
///
///    \date 3 sep. 2024
///
///    \author      Victor Morales, vmm6 (at) embention.com
///    Company      Embention S.A.
///
///    Irq_manager class implementation.
///

#include <Irq_manager.h>
#include <GIC.h>

namespace Zusp
{

	Irq_manager::Irq_handler Irq_manager::irq_handlers[GIC_n_irqs];
		
	bool Irq_manager::irq_hndl_set[GIC_n_irqs];
	
	bool Irq_manager::initialized = false;

	/// Generic handler for IRQs.
	/// \param[in] irq_id        ID of interrupt to be handled.
	/// \return none.
	void Irq_manager::exc_irq_handler(Uint16 irq_id)
	{ 
		/// \alg
		/// <ul>
		/// <li> Get signaled irq
		Uint16 signald_irq = GIC::get_signald_irq();

		/// <li> Check if the irq id parameter match with signaled irq
		if(irq_id == signald_irq)
		{
			irq_handlers[irq_id].handler(irq_handlers[irq_id].data);
		}

		// <li>  Any action required if the signaled irq id not match with the required
		/// </ul>
	}


	/// Interrupt manager initialization.
	/// \return error code.
	Uint8 Irq_manager::init()
	{
		/// \alg
		/// <ul>
		/// <li>  Initialize GIC distributor
		GIC::init_distr();
		/// <li>  Set Exception irq handler
		Intr_vector::excep_vec_table[exc_id_irq_int].handler = (Exception::Exc_handler)(exc_irq_handler);
		Intr_vector::excep_vec_table[exc_id_irq_int].data = (void *)0;

		/// <li> Initiallize the array irq_hndl_set to false
		for(Uint16 iter = 0; iter < GIC_n_irqs; iter++)
		{
			irq_hndl_set[iter] = false;
		}
		/// <li>  Initialization done
		initialized = true;
		return 0;
		/// </ul>
	}
	
	/// Check interrupt manager initialization .
	/// \return interrupt manager initialization status.
	bool Irq_manager::check_init()
	{
		/// \alg
		/// <ul>
		/// <li> Return initialization status
		return initialized;
		/// </ul>
	}

	/// Constructor.
	/// \param[in] id             interrupt id.
	/// \param[in] group        security group.
	/// \param[in] targets        core target mask.
	/// \param[in] handler        interrupt handler.
	/// \return none.
	Irq_manager::Irq_manager(Uint16 id, Irq_manager::Security group, Uint8 targets, Irq_handler handler) : id(id), group(group), core_targets(targets)
	{
		/// \alg
		/// <ul>
		/// <li> Check if the manager is not initialize, in that case it does it.
		if(check_init() == false)
		{
			init();
		}

		/// <li> Set the irq handler
		set_handler(handler);
		/// <li> Enable the irq
		enable();
		/// </ul>
	}

	
	/// Constructor with secure group as default.
	/// \param[in] id             interrupt id.
	/// \param[in] targets        core target mask.
	/// \param[in] handler        interrupt handler.
	/// \return none.
	Irq_manager::Irq_manager(Uint16 id, Uint8 targets, Irq_handler handler) : id(id), core_targets(targets) 
	{
		/// \alg
		/// <ul>
		/// <li> Check if the manager is not initialize, in that case it does it.
		if(check_init() == false)
		{
			init();
		}
		/// <li> Set the irq handler
		set_handler(handler);
		/// <li> Set security group
		set_security(secure);
		/// <li> Enable the irq
		enable();
		/// </ul>
	}


	/// Set interrupt handler.
	/// \param[in] handler        interrupt handler.
	/// \return error code.
	Uint8 Irq_manager::set_handler(Irq_handler handler)
	{
		/// \alg
		/// <ul>
		Uint8 ret;
		Uint16 irq_id = get_id();
		/// <li> Check if irq id is valid
		if((irq_id > GIC_n_irqs) || (irq_id < 0))
		{
			ret = 1;
		}
		/// <li> Check the validty of handler and data, and set them if they are valid
		else if((handler.handler == NULL) ||(handler.data == NULL))
		{
			ret = 2;
		}
		else
		{	
			irq_handlers[irq_id].handler = handler.handler;
			irq_handlers[irq_id].data = handler.data;
			irq_hndl_set[irq_id] = true;
			ret = 0;
		}

		/// <li> Return error code
		return ret;
		/// </ul>
	}

	/// Add specific core to the targets.
	/// \param[in] target        core id.
	/// \return error code.
	Uint8 Irq_manager::add_target(Uint8 target)
	{
		/// \alg
		/// <ul>
		Uint8 ret;
		/// <li> Check if the target core id is valid (under the limit)
		if(target < max_n_cores)
		{
			/// <ul>
			/// <li>  Get mask for core id
			Uint8 target_mask = 1 << target;
			/// <li>  Set target mask
			core_targets |= target_mask;
			ret = 0;
			/// </ul>
		}
		else
		{
			ret = 1;
		}

		/// <li> Return error code
		return ret;
		/// </ul>
	}

	/// Remove specific core from the targets.
	/// \param[in] target        core id.
	/// \return error code.
	Uint8 Irq_manager::remove_target(Uint8 target)
	{
		/// \alg
		/// <ul>
		Uint8 ret;
		/// <li> Check if the target core id is valid (under the limit)
		if(target < max_n_cores)
		{
			/// <ul>
			/// <li>   Get mask for core id
			Uint8 target_mask = 1 << target;
			/// <li>  Set target mask
			core_targets &= ~target_mask;
			ret = 0;
			/// </ul>
		}
		else
		{
			ret = 1;
		}
		/// <li> Return error code
		return ret; 
		/// </ul>
	}

	/// Set core targets (each bit is a core).
	/// \param[in] targets        core target mask.
	/// \return error code.
	Uint8 Irq_manager::set_targets(Uint8 targets)
	{
		/// \alg
		/// <ul>
		Uint8 ret;
		/// <li> Check if the target mask is valid (under the limit)
		Uint8 mask_limit = (1U << max_n_cores);
		if(targets < mask_limit)
		{
			/// <ul>
			/// <li>  Set target mask
			core_targets = targets;
			ret = 0;
			/// </ul>
		}
		else
		{
			ret = 1;
		}
		/// <li> Return error code
		return ret;
		/// </ul>
	}

	/// Security group setter.
	/// \param[in] grp        security group.
	/// \return error code.
	Uint8 Irq_manager::set_security(Security grp)
	{
		/// \alg
		/// <ul>
		Uint8 ret;
		/// <li> Check if the security group is valid
		if((grp != secure) && (grp != nonsecure))
		{
			ret = 1;
		}
		else
		{
			/// <ul>
			/// <li> Set security group
			group = grp;
			ret = 0;
			/// </ul>
		}
		/// <li> Return error code
		return 0;
		/// </ul>
	}

	/// Current security group getter.
	/// \return security group.
	Irq_manager::Security Irq_manager::get_security()
	{
		/// \alg
		/// <ul>
		/// <li> Return security group
		return group;
		/// </ul>
	}

	/// Interrupt id getter.
	/// \return interrupt id.
	Uint16 Irq_manager::get_id()
	{
		/// \alg
		/// <ul>
		/// <li> Return interrupt id
		return id;
		/// </ul>
	}

	/// Interrupt enabler
	/// \return error code.
	Uint8 Irq_manager::enable()
	{	
		/// \alg
		/// <ul>
		Uint8 ret;
		Uint16 irq_id = get_id();
		/// <li> Check if irq id is valid
		if((irq_id > GIC_n_irqs) || (irq_id < 0))
		{
			ret = 1;
		}
		else
		{
			/// <ul>
			/// <li> Enable interrupt
			enabled = true;
			Zusp::GIC::enable(irq_id);
			ret = 0;
			/// </ul>
		}
		/// <li> Return error code
		return ret;
		/// </ul>
	}

	/// Interrupt disabler.
	/// \return error code.
	Uint8 Irq_manager::disable()
	{	
		/// \alg
		/// <ul>
		/// <li> 
		Uint8 ret;
		Uint16 irq_id = get_id();
		/// <li> Check if irq id is valid
		if((irq_id > GIC_n_irqs) || (irq_id < 0))
		{
			ret = 1;
		}
		else
		{
			/// <ul>
			/// <li> Disable interrupt
			enabled = false;
			Zusp::GIC::disable(irq_id);
			ret = 0;
			/// </ul>
		}
		/// <li> Return error code
		return ret;
		/// </ul>
	}

	/// Enablement getter.
	/// \return enable or not.
	bool Irq_manager::get_status()
	{	
		/// \alg
		/// <ul>
		/// <li> Return enabling status
		return enabled;
		/// </ul>
	}



	/// Trigger interrupt.
	/// \return error code.
	Uint8 Irq_manager::signal()
	{
		/// \alg
		/// <ul>
		Uint8 ret = 0;
		/// <li> Get irq id and security group
		Uint16 irq_id = get_id();
		Security sec_grp = get_security();

		/// <li>  Check if irq is part of SGIs
		if(irq_id < GIC_sgi_idx || irq_id >= GIC_ppi_idx)
		{
			ret = 1;
		}
		/// <li>  Check manager initialization
		else if(check_init() == false)
		{
			ret = 2;
		}
		/// <li>  Check if irq is enabled
		else if(get_status() == false)
		{
			ret = 3;
		}
		/// <li>  Check if irq handler is set
		else if(irq_hndl_set[irq_id] == false)
		{
			ret = 4;
		}
		else
		{
			/// <ul>
			/// <li>  Set the interrupt id as data to IRQ exception
			Intr_vector::excep_vec_table[exc_id_irq_int].data = (void*)irq_id;

			/// <li>  Signal sgi
			if(sec_grp == secure)
			{
				Zusp::GIC::trigg_sec_sgi(irq_id, core_targets);
			}
			else if (sec_grp == nonsecure)
			{
				Zusp::GIC::trigg_nsec_sgi(irq_id, core_targets);
			}
			/// <li>  Secure group unknown
			else
			{
				ret = 5;
			}
			/// </ul>
		}
		
		return ret;
		/// </ul>
	}


}