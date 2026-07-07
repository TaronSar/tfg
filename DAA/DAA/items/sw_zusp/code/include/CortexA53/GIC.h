///    \file GIC.h
///
///    \date 29 ago. 2024
///
///    \author      Victor Morales, vmm6 (at) embention.com
///    Company      Embention S.A.
///
///    GIC class header.
///

#ifndef ZUSP_GIC_H_
#define ZUSP_GIC_H_

#include <Entypes.h> //from Vlibs

namespace Zusp
{
    class GIC
    {
        public:

            // Interrupts groups
            typedef enum
            {
                group_0,    // Secure group
                group_1,    // Non-secure group
            } 
            Interrupt_group;

            // Interrupts model
            typedef enum
            {
                N_N,         // All processors receive the interrupt independenly
                one_N,       // Only one processor handles this interrupt
            } 
            Interrupt_model;

            // Interrupts Assertment
            typedef enum
            {
                level_sen,    // Remains asserted until the interrupt is cleared   
                edge_trig     // Deasserted whenever the level is not active
            } 
            Interrupt_assert;



        /// Distributor initialization.
        /// \return none.
        static void init_distr();
        /// CPU interface initialization.
        /// \return none.
        static void init_interface();
    
        /// Interrupt enabling.
        /// \param[in] intr_id        Interrupt identification.
        /// \return none.
        static void enable(Uint16 intr_id);
        
        /// Interrupt disabling.
        /// \param[in] intr_id        Interrupt identification.
        /// \return none.
        static void disable(Uint16 intr_id);
        
        /// Interrupt setting pending.
        /// \param[in] intr_id        Interrupt identification.
        /// \return none.
        static void set_pending(Uint16 intr_id);
        
        /// Interrupt clearing pending.
        /// \param[in] intr_id        Interrupt identification.
        /// \return none.
        static void clr_pending(Uint16 intr_id);
        
        
        /// Interrupt setting active.
        /// \param[in] intr_id        Interrupt identification.
        /// \return none.
        static void set_active(Uint16 intr_id);
        
        /// Interrupt clearing active.
        /// \param[in] intr_id        Interrupt identification.
        /// \return none.
        static void clr_active(Uint16 intr_id);
    
        /// Interrupt group assignation.
        /// \param[in] intr_id         Interrupt identification.
        /// \param[in] group           group identification.
        /// \return none.
        static void assign_group(Uint16 intr_id, Interrupt_group group);
        
        /// Group enabling.
        /// \param[in] group           group identification.
        /// \return none.
        static void enable_group(Interrupt_group group);
    
        /// Group disabling.
        /// \param[in] group           group identification.
        /// \return none.
        static void disable_group(Interrupt_group group);

        
        /// Interrupt targeting to specific CPU core.
        /// \param[in] intr_id         Interrupt identification.
        /// \param[in] target          Cpu target.
        /// \return none.
        static void add_target(Uint16 intr_id, Uint8 target);
        
        /// Remove interrupt targeting to specific CPU core.
        /// \param[in] intr_id         Interrupt identification.
        /// \param[in] target          Cpu target.
        /// \return none.
        static void remove_target(Uint16 intr_id, Uint8 target);
        
        /// Interrupt targeting to multiple CPU core.
        /// \param[in] intr_id         Interrupt identification.
        /// \param[in] target          Cpu targets.
        /// \return none.
        static void set_targets(Uint16 intr_id, Uint8 targets);
        
        /// Configure assertion and model of interrupt.
        /// \param[in] intr_id         Interrupt identification.
        /// \param[in] assert          Interrupt assert.
        /// \param[in] model           Interrupt model.
        /// \return none.
        static void set_config(Uint16 intr_id, Interrupt_assert assert, Interrupt_model model);
    
        
        /// Trigger secure sgi to specific target.
        /// \param[in] intr_id          Interrupt identification.
        /// \param[in] cpu_target_list  Cpu core target.
        /// \return none.
        static void trigg_sec_sgi(Uint16 intr_id, Uint8 cpu_target_list);
        
        /// Trigger non-secure sgi to specific target.
        /// \param[in] intr_id          Interrupt identification.
        /// \param[in] cpu_target_list  Cpu core target.
        /// \return none.
        static void trigg_nsec_sgi(Uint16 intr_id, Uint8 cpu_target_list);
        
        /// Set SGI as pending.
        /// \param[in] intr_id          Interrupt identification.
        /// \param[in] cpu_target_list  Cpu core target.
        /// \return none.
        static void set_pend_sgi(Uint16 intr_id, Uint8 cpu_target_list);
        
        /// Clear pending SGI.
        /// \param[in] intr_id          Interrupt identification.
        /// \param[in] cpu_target_list  Cpu core target.
        /// \return none.
        static void clr_pend_sgi(Uint16 intr_id, Uint8 cpu_target_list);

        
        /// Set cpu interface priority.
        /// \param[in] priority          Priority level.
        /// \return none.
        static void set_iface_prior(Uint8 priority);
        
        /// Set interrupt priority.
        /// \param[in] priority          Priority level.
        /// \return none.
        static void set_intr_prior(Uint16 intr_id, Uint8 priority);

        /// Get signaled irq.
        /// \return signaled irq id.
        static Uint16 get_signald_irq();


        private:
            GIC(); ///< = delete
            GIC(const GIC& orig); ///< = delete
            ~GIC(); ///< = delete
            GIC& operator=(const GIC& orig); ///< = delete

    };
}

#endif