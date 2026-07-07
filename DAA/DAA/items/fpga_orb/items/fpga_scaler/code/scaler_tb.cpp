/**
* This file is part of ac^2SLAM.
*
* Copyright (C) 2021 Cheng Wang <wangcheng at stu dot xjtu dot edu dot cn> (Xi'an Jiaotong University)
* For more information see <https://github.com/SLAM-Hardware/acSLAM>
*
* ac^2SLAM is free software: you can redistribute it and/or modify
* it under the terms of the GNU General Public License as published by
* the Free Software Foundation, either version 3 of the License, or
* (at your option) any later version.
*
* ac^2SLAM is distributed in the hope that it will be useful,
* but WITHOUT ANY WARRANTY; without even the implied warranty of
* MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
* GNU General Public License for more details.
*
* You should have received a copy of the GNU General Public License
* along with ac^2SLAM. If not, see <http://www.gnu.org/licenses/>.
*/
/**
 * SC: modificado para soportar AXI stream video y configuración por AXIlite
 * Modificaciones:
 *  - generación de los parámetros de conf.
 *  - lectura de stream de salida teniendo en cuenta el last de fin de linea
 *  - IMPORTANTE: los valores new_width y new_height deben introducirse a mano en la versión AXILITE
 */

#include "scaler.h"
#include "img_1440.h"
#include <fstream>
#define PRINT_RES

using namespace std;
int main()
{
    int width = 1440;//1241;
    int height = 1080; //376;

    hls::stream<ap_axiu<INPUT_STREAM_BIT, 1, 1, 1> > srcStream;
    hls::stream<ap_axiu<OUTPUT_STREAM_BIT, 1, 1, 1> > outStream;

#ifdef AXILITE
    ap_ufixed<16, 2> scale ;
    ap_ufixed<16, 2> scale_in ;
    ap_uint<32> p_scale;
    ap_uint<32> p_inv_scale;

    //SC: generación de los parámetros de control
	scale = SCALE;
	scale_in = 1/SCALE;
	p_scale.range(15,0) = scale.range(15, 0);
	p_scale.range(31,16) = 0;
	p_inv_scale.range(15,0) = scale_in.range(15,0);
	p_inv_scale.range(31,16) = 0;
#else
    hls::stream<ap_axiu<32, 1, 1, 1> > cfgoutStream;
    hls::stream<ap_axiu<32, 1, 1, 1> > cfgStream;

    ap_axiu<32, 1, 1, 1> cfgin;
    cfgin.data = width;
    cfgin.keep = 0xF;
    cfgin.last = 0;
    cfgStream.write(cfgin);
    cfgin.data = height;
    cfgin.keep = 0xF;
    cfgin.last = 0;
    cfgStream.write(cfgin);
    ap_ufixed<16, 2> scale_in = SCALE;
    cfgin.data.range(15, 0) = scale_in.range(15, 0);
    cfgin.data.range(31, 16) = 0;
    cfgin.keep = 0xF;
    cfgin.last = 0;
    cfgStream.write(cfgin);
    scale_in = 1/SCALE;
    cfgin.data.range(15, 0) = scale_in.range(15, 0);
    cfgin.data.range(31, 16) = 0;
    cfgin.keep = 0xF;
    cfgin.last = 1;
    cfgStream.write(cfgin);
#endif

    ap_axiu<INPUT_STREAM_BIT, 1, 1, 1> src;
    ap_uint<INPUT_BIT> data = 0;

    int cnt = 0;
    for (int i = 0; i< width*height; i++)
    {
        data.range((cnt+1)*PIXEL_BIT-1, cnt*PIXEL_BIT) = img1080_gray[i/width][i%width];
        cnt++;
        if (cnt == INPUT_PIXEL_NUM)
        {
            src.data = data;
            src.keep = 0xFFFFFFFFFFFFFFFF;
            if (i == width*height-1)
                src.last = 1;
            else
                src.last = 0;
            srcStream.write(src);
            cnt = 0;
            data= 0;
        }
    }
    if (cnt > 0)
    {
        src.data = data;
        src.keep = 0xFFFFFFFFFFFFFFFF;
        src.last = 1;
        srcStream.write(src);
    }
#ifdef AXILITE
    scaler(srcStream, outStream, width, height, p_scale, p_inv_scale);
    // TODO: leer los parámetros calculados a través de axilite
    int new_width = 640;
    int new_height = 480;
#else
    scaler(cfgStream, srcStream, cfgoutStream, outStream);
    int new_width = cfgoutStream.read().data;
    int new_height = cfgoutStream.read().data;
#endif

    cout << new_width << endl;
    cout << new_height << endl;

    ap_uint<PIXEL_BIT> new_img[HEIGHT][WIDTH];
    ap_axiu<OUTPUT_STREAM_BIT,1,1,1> outData;
    //ap_axiu<1> new_last[HEIGHT];
    cnt = 0;
    int cnt_last=0; //SC
    do
    {
        outData = outStream.read();
        ap_uint<OUTPUT_BIT> tmp = outData.data;
        //new_last[HEIGHT][WIDTH]=outData.last; //SC
        ap_uint<1> auxlast= outData.last;
        if (auxlast==1) { cnt_last++;}

        for (int i=0; i<OUTPUT_PIXEL_NUM; i++)
        {
            if (cnt < new_height*new_width)
            {
                new_img[cnt/new_width][cnt%new_width] = tmp.range(PIXEL_BIT-1,0);
                tmp = tmp >> PIXEL_BIT;
            }
            cnt++;
        }
    //}while (outData.last == 0 && cnt < new_height*new_width);
	}while (cnt < new_height*new_width);	//SC: last=1 al final de cada linea

    cout << "numero de last=" << cnt_last << " "<< endl;

#ifdef PRINT_RES
    for (int i = 0; i < new_height; i++)
    {
        for (int j = 0; j < new_width; j++)
             cout << new_img[i][j] << " ";
         cout << endl;
    }
#endif

    ofstream ofile;
    ofile.open("../../../../result.txt");
    ofile << new_width << endl;
    ofile << new_height << endl;
    for (int i = 0; i < new_height; i++)
    {
        for (int j = 0; j < new_width; j++)
            ofile << new_img[i][j] << endl;
    }

    cout <<"-----------------------finish-------------------------"<< endl;
}
