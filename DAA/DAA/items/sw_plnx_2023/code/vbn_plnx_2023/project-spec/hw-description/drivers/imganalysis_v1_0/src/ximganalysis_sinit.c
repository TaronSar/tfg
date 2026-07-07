// ==============================================================
// Vitis HLS - High-Level Synthesis from C, C++ and OpenCL v2023.1 (64-bit)
// Tool Version Limit: 2023.05
// Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
// Copyright 2022-2023 Advanced Micro Devices, Inc. All Rights Reserved.
// 
// ==============================================================
#ifndef __linux__

#include "xstatus.h"
#include "xparameters.h"
#include "ximganalysis.h"

extern XImganalysis_Config XImganalysis_ConfigTable[];

XImganalysis_Config *XImganalysis_LookupConfig(u16 DeviceId) {
	XImganalysis_Config *ConfigPtr = NULL;

	int Index;

	for (Index = 0; Index < XPAR_XIMGANALYSIS_NUM_INSTANCES; Index++) {
		if (XImganalysis_ConfigTable[Index].DeviceId == DeviceId) {
			ConfigPtr = &XImganalysis_ConfigTable[Index];
			break;
		}
	}

	return ConfigPtr;
}

int XImganalysis_Initialize(XImganalysis *InstancePtr, u16 DeviceId) {
	XImganalysis_Config *ConfigPtr;

	Xil_AssertNonvoid(InstancePtr != NULL);

	ConfigPtr = XImganalysis_LookupConfig(DeviceId);
	if (ConfigPtr == NULL) {
		InstancePtr->IsReady = 0;
		return (XST_DEVICE_NOT_FOUND);
	}

	return XImganalysis_CfgInitialize(InstancePtr, ConfigPtr);
}

#endif

