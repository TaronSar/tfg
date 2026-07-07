#include <Assertions.h>
#include <Memmgr.h>
#include <stdio.h>

static const Uint32 Kbyte      = 1024;
static const Uint32 Mbyte      = 1024 * 1024;
static const Uint32 Gbyte      = 1024 * 1024 * 1024;
static const Uint32 int_buf_sz = 0;
static const Uint64 ext_buf_sz = 1 * Mbyte;

Uint16 int_buf[int_buf_sz];
Uint16 ext_buf[ext_buf_sz];

namespace Base
{
    Memmgr::Memmgr(Allocator& internal_alloc, Allocator& external_alloc) :
        init_stage(true)
    {
        allocators[internal] = &internal_alloc;
        allocators[external] = &external_alloc;
    }

    Memmgr& Memmgr::get_instance()
    {
        static Allocator internal_alloc(int_buf, int_buf_sz);
        static Allocator external_alloc(ext_buf, ext_buf_sz);

        static Memmgr memmgr_c1(internal_alloc, external_alloc);  // instance for C1 low and C1 high

        return memmgr_c1;
    }

    void Memmgr::close_allocation()
    {
        allocators[internal]->close_allocation();
        allocators[external]->close_allocation();

        init_stage = false;
    }

    Allocator& Memmgr::get_allocator(Type type0)
    {
        Base::Assertions::runtime(init_stage && (type0 < mem_type_max));
        return *get_instance().allocators[type0];
    }

}
