// ==============================================================
// Vitis HLS - High-Level Synthesis from C, C++ and OpenCL v2023.1 (64-bit)
// Tool Version Limit: 2023.05
// Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
// Copyright 2022-2023 Advanced Micro Devices, Inc. All Rights Reserved.
// 
// ==============================================================
/***************************** Include Files *********************************/
#include "ximganalysis.h"

/************************** Function Implementation *************************/
#ifndef __linux__
int XImganalysis_CfgInitialize(XImganalysis *InstancePtr, XImganalysis_Config *ConfigPtr) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(ConfigPtr != NULL);

    InstancePtr->Histo_data_BaseAddress = ConfigPtr->Histo_data_BaseAddress;
    InstancePtr->IsReady = XIL_COMPONENT_IS_READY;

    return XST_SUCCESS;
}
#endif

u32 XImganalysis_Get_npix(XImganalysis *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XImganalysis_ReadReg(InstancePtr->Histo_data_BaseAddress, XIMGANALYSIS_HISTO_DATA_ADDR_NPIX_DATA);
    return Data;
}

u32 XImganalysis_Get_npix_vld(XImganalysis *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XImganalysis_ReadReg(InstancePtr->Histo_data_BaseAddress, XIMGANALYSIS_HISTO_DATA_ADDR_NPIX_CTRL);
    return Data & 0x1;
}

u32 XImganalysis_Get_sumval(XImganalysis *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XImganalysis_ReadReg(InstancePtr->Histo_data_BaseAddress, XIMGANALYSIS_HISTO_DATA_ADDR_SUMVAL_DATA);
    return Data;
}

u32 XImganalysis_Get_sumval_vld(XImganalysis *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XImganalysis_ReadReg(InstancePtr->Histo_data_BaseAddress, XIMGANALYSIS_HISTO_DATA_ADDR_SUMVAL_CTRL);
    return Data & 0x1;
}

void XImganalysis_Set_rows(XImganalysis *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XImganalysis_WriteReg(InstancePtr->Histo_data_BaseAddress, XIMGANALYSIS_HISTO_DATA_ADDR_ROWS_DATA, Data);
}

u32 XImganalysis_Get_rows(XImganalysis *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XImganalysis_ReadReg(InstancePtr->Histo_data_BaseAddress, XIMGANALYSIS_HISTO_DATA_ADDR_ROWS_DATA);
    return Data;
}

void XImganalysis_Set_cols(XImganalysis *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XImganalysis_WriteReg(InstancePtr->Histo_data_BaseAddress, XIMGANALYSIS_HISTO_DATA_ADDR_COLS_DATA, Data);
}

u32 XImganalysis_Get_cols(XImganalysis *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XImganalysis_ReadReg(InstancePtr->Histo_data_BaseAddress, XIMGANALYSIS_HISTO_DATA_ADDR_COLS_DATA);
    return Data;
}

u32 XImganalysis_Get_histo_BaseAddress(XImganalysis *InstancePtr) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    return (InstancePtr->Histo_data_BaseAddress + XIMGANALYSIS_HISTO_DATA_ADDR_HISTO_BASE);
}

u32 XImganalysis_Get_histo_HighAddress(XImganalysis *InstancePtr) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    return (InstancePtr->Histo_data_BaseAddress + XIMGANALYSIS_HISTO_DATA_ADDR_HISTO_HIGH);
}

u32 XImganalysis_Get_histo_TotalBytes(XImganalysis *InstancePtr) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    return (XIMGANALYSIS_HISTO_DATA_ADDR_HISTO_HIGH - XIMGANALYSIS_HISTO_DATA_ADDR_HISTO_BASE + 1);
}

u32 XImganalysis_Get_histo_BitWidth(XImganalysis *InstancePtr) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    return XIMGANALYSIS_HISTO_DATA_WIDTH_HISTO;
}

u32 XImganalysis_Get_histo_Depth(XImganalysis *InstancePtr) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    return XIMGANALYSIS_HISTO_DATA_DEPTH_HISTO;
}

u32 XImganalysis_Write_histo_Words(XImganalysis *InstancePtr, int offset, word_type *data, int length) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr -> IsReady == XIL_COMPONENT_IS_READY);

    int i;

    if ((offset + length)*4 > (XIMGANALYSIS_HISTO_DATA_ADDR_HISTO_HIGH - XIMGANALYSIS_HISTO_DATA_ADDR_HISTO_BASE + 1))
        return 0;

    for (i = 0; i < length; i++) {
        *(int *)(InstancePtr->Histo_data_BaseAddress + XIMGANALYSIS_HISTO_DATA_ADDR_HISTO_BASE + (offset + i)*4) = *(data + i);
    }
    return length;
}

u32 XImganalysis_Read_histo_Words(XImganalysis *InstancePtr, int offset, word_type *data, int length) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr -> IsReady == XIL_COMPONENT_IS_READY);

    int i;

    if ((offset + length)*4 > (XIMGANALYSIS_HISTO_DATA_ADDR_HISTO_HIGH - XIMGANALYSIS_HISTO_DATA_ADDR_HISTO_BASE + 1))
        return 0;

    for (i = 0; i < length; i++) {
        *(data + i) = *(int *)(InstancePtr->Histo_data_BaseAddress + XIMGANALYSIS_HISTO_DATA_ADDR_HISTO_BASE + (offset + i)*4);
    }
    return length;
}

u32 XImganalysis_Write_histo_Bytes(XImganalysis *InstancePtr, int offset, char *data, int length) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr -> IsReady == XIL_COMPONENT_IS_READY);

    int i;

    if ((offset + length) > (XIMGANALYSIS_HISTO_DATA_ADDR_HISTO_HIGH - XIMGANALYSIS_HISTO_DATA_ADDR_HISTO_BASE + 1))
        return 0;

    for (i = 0; i < length; i++) {
        *(char *)(InstancePtr->Histo_data_BaseAddress + XIMGANALYSIS_HISTO_DATA_ADDR_HISTO_BASE + offset + i) = *(data + i);
    }
    return length;
}

u32 XImganalysis_Read_histo_Bytes(XImganalysis *InstancePtr, int offset, char *data, int length) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr -> IsReady == XIL_COMPONENT_IS_READY);

    int i;

    if ((offset + length) > (XIMGANALYSIS_HISTO_DATA_ADDR_HISTO_HIGH - XIMGANALYSIS_HISTO_DATA_ADDR_HISTO_BASE + 1))
        return 0;

    for (i = 0; i < length; i++) {
        *(data + i) = *(char *)(InstancePtr->Histo_data_BaseAddress + XIMGANALYSIS_HISTO_DATA_ADDR_HISTO_BASE + offset + i);
    }
    return length;
}

