// ==============================================================
// Vitis HLS - High-Level Synthesis from C, C++ and OpenCL v2023.1 (64-bit)
// Tool Version Limit: 2023.05
// Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
// Copyright 2022-2023 Advanced Micro Devices, Inc. All Rights Reserved.
// 
// ==============================================================
#ifndef XIMGANALYSIS_H
#define XIMGANALYSIS_H

#ifdef __cplusplus
extern "C" {
#endif

/***************************** Include Files *********************************/
#ifndef __linux__
#include "xil_types.h"
#include "xil_assert.h"
#include "xstatus.h"
#include "xil_io.h"
#else
#include <stdint.h>
#include <assert.h>
#include <dirent.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>
#include <stddef.h>
#endif
#include "ximganalysis_hw.h"

/**************************** Type Definitions ******************************/
#ifdef __linux__
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef uint64_t u64;
#else
typedef struct {
    u16 DeviceId;
    u64 Histo_data_BaseAddress;
} XImganalysis_Config;
#endif

typedef struct {
    u64 Histo_data_BaseAddress;
    u32 IsReady;
} XImganalysis;

typedef u32 word_type;

/***************** Macros (Inline Functions) Definitions *********************/
#ifndef __linux__
#define XImganalysis_WriteReg(BaseAddress, RegOffset, Data) \
    Xil_Out32((BaseAddress) + (RegOffset), (u32)(Data))
#define XImganalysis_ReadReg(BaseAddress, RegOffset) \
    Xil_In32((BaseAddress) + (RegOffset))
#else
#define XImganalysis_WriteReg(BaseAddress, RegOffset, Data) \
    *(volatile u32*)((BaseAddress) + (RegOffset)) = (u32)(Data)
#define XImganalysis_ReadReg(BaseAddress, RegOffset) \
    *(volatile u32*)((BaseAddress) + (RegOffset))

#define Xil_AssertVoid(expr)    assert(expr)
#define Xil_AssertNonvoid(expr) assert(expr)

#define XST_SUCCESS             0
#define XST_DEVICE_NOT_FOUND    2
#define XST_OPEN_DEVICE_FAILED  3
#define XIL_COMPONENT_IS_READY  1
#endif

/************************** Function Prototypes *****************************/
#ifndef __linux__
int XImganalysis_Initialize(XImganalysis *InstancePtr, u16 DeviceId);
XImganalysis_Config* XImganalysis_LookupConfig(u16 DeviceId);
int XImganalysis_CfgInitialize(XImganalysis *InstancePtr, XImganalysis_Config *ConfigPtr);
#else
int XImganalysis_Initialize(XImganalysis *InstancePtr, const char* InstanceName);
int XImganalysis_Release(XImganalysis *InstancePtr);
#endif


u32 XImganalysis_Get_npix(XImganalysis *InstancePtr);
u32 XImganalysis_Get_npix_vld(XImganalysis *InstancePtr);
u32 XImganalysis_Get_sumval(XImganalysis *InstancePtr);
u32 XImganalysis_Get_sumval_vld(XImganalysis *InstancePtr);
void XImganalysis_Set_rows(XImganalysis *InstancePtr, u32 Data);
u32 XImganalysis_Get_rows(XImganalysis *InstancePtr);
void XImganalysis_Set_cols(XImganalysis *InstancePtr, u32 Data);
u32 XImganalysis_Get_cols(XImganalysis *InstancePtr);
u32 XImganalysis_Get_histo_BaseAddress(XImganalysis *InstancePtr);
u32 XImganalysis_Get_histo_HighAddress(XImganalysis *InstancePtr);
u32 XImganalysis_Get_histo_TotalBytes(XImganalysis *InstancePtr);
u32 XImganalysis_Get_histo_BitWidth(XImganalysis *InstancePtr);
u32 XImganalysis_Get_histo_Depth(XImganalysis *InstancePtr);
u32 XImganalysis_Write_histo_Words(XImganalysis *InstancePtr, int offset, word_type *data, int length);
u32 XImganalysis_Read_histo_Words(XImganalysis *InstancePtr, int offset, word_type *data, int length);
u32 XImganalysis_Write_histo_Bytes(XImganalysis *InstancePtr, int offset, char *data, int length);
u32 XImganalysis_Read_histo_Bytes(XImganalysis *InstancePtr, int offset, char *data, int length);

#ifdef __cplusplus
}
#endif

#endif
