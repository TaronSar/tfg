// ==============================================================
// Vitis HLS - High-Level Synthesis from C, C++ and OpenCL v2023.1 (64-bit)
// Tool Version Limit: 2023.05
// Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
// Copyright 2022-2023 Advanced Micro Devices, Inc. All Rights Reserved.
// 
// ==============================================================
// histo_data
// 0x000 : reserved
// 0x004 : reserved
// 0x008 : reserved
// 0x00c : reserved
// 0x010 : Data signal of npix
//         bit 31~0 - npix[31:0] (Read)
// 0x014 : Control signal of npix
//         bit 0  - npix_ap_vld (Read/COR)
//         others - reserved
// 0x020 : Data signal of sumval
//         bit 31~0 - sumval[31:0] (Read)
// 0x024 : Control signal of sumval
//         bit 0  - sumval_ap_vld (Read/COR)
//         others - reserved
// 0x030 : Data signal of rows
//         bit 31~0 - rows[31:0] (Read/Write)
// 0x034 : reserved
// 0x038 : Data signal of cols
//         bit 31~0 - cols[31:0] (Read/Write)
// 0x03c : reserved
// 0x400 ~
// 0x7ff : Memory 'histo' (256 * 32b)
//         Word n : bit [31:0] - histo[n]
// (SC = Self Clear, COR = Clear on Read, TOW = Toggle on Write, COH = Clear on Handshake)

#define XIMGANALYSIS_HISTO_DATA_ADDR_NPIX_DATA   0x010
#define XIMGANALYSIS_HISTO_DATA_BITS_NPIX_DATA   32
#define XIMGANALYSIS_HISTO_DATA_ADDR_NPIX_CTRL   0x014
#define XIMGANALYSIS_HISTO_DATA_ADDR_SUMVAL_DATA 0x020
#define XIMGANALYSIS_HISTO_DATA_BITS_SUMVAL_DATA 32
#define XIMGANALYSIS_HISTO_DATA_ADDR_SUMVAL_CTRL 0x024
#define XIMGANALYSIS_HISTO_DATA_ADDR_ROWS_DATA   0x030
#define XIMGANALYSIS_HISTO_DATA_BITS_ROWS_DATA   32
#define XIMGANALYSIS_HISTO_DATA_ADDR_COLS_DATA   0x038
#define XIMGANALYSIS_HISTO_DATA_BITS_COLS_DATA   32
#define XIMGANALYSIS_HISTO_DATA_ADDR_HISTO_BASE  0x400
#define XIMGANALYSIS_HISTO_DATA_ADDR_HISTO_HIGH  0x7ff
#define XIMGANALYSIS_HISTO_DATA_WIDTH_HISTO      32
#define XIMGANALYSIS_HISTO_DATA_DEPTH_HISTO      256

