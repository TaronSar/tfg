/*
 * Copyright (C) 2018 - 2022 Xilinx, Inc. All rights reserved.
 * Copyright (C) 2022 - 2024 Advanced Micro Devices, Inc.  All rights reserved
 *
 * Redistribution and use in source and binary forms, with or without modification,
 * are permitted provided that the following conditions are met:
 *
 * 1. Redistributions of source code must retain the above copyright notice,
 *    this list of conditions and the following disclaimer.
 * 2. Redistributions in binary form must reproduce the above copyright notice,
 *    this list of conditions and the following disclaimer in the documentation
 *    and/or other materials provided with the distribution.
 * 3. The name of the author may not be used to endorse or promote products
 *    derived from this software without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR IMPLIED
 * WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF
 * MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT
 * SHALL THE AUTHOR BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
 * EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT
 * OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
 * INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
 * CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
 * IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY
 * OF SUCH DAMAGE.
 *
 */

/** Connection handle for a UDP Server session */

#include "udp_perf_server.h"

extern struct netif server_netif;
static struct udp_pcb *pcb;
static struct perf_stats server;
/* Report interval in ms */
#define REPORT_INTERVAL_TIME (INTERIM_REPORT_INTERVAL * 20)

void print_app_header(void)
{
	xil_printf("UDP server listening on port %d\r\n",
			UDP_CONN_PORT);
	xil_printf("On Host: Run $iperf -c %s -i %d -t 300 -u -b <bandwidth>\r\n",
			inet_ntoa(server_netif.ip_addr),
			INTERIM_REPORT_INTERVAL);

}

static void print_udp_conn_stats(void)
{
	xil_printf("[%3d] local %s port %d connected with ",
			server.client_id, inet_ntoa(server_netif.ip_addr),
			UDP_CONN_PORT);
	xil_printf("%s port %d\r\n", inet_ntoa(pcb->remote_ip),
			pcb->remote_port);
	xil_printf("[ ID] Interval\t     Transfer     Bandwidth\t");
	xil_printf("    Lost/Total Datagrams\n\r");
}

static void stats_buffer(char* outString,
		double data, enum measure_t type)
{
	int conv = KCONV_UNIT;
	const char *format;
	double unit = 1024.0;

	if (type == SPEED)
		unit = 1000.0;

	while (data >= unit && conv <= KCONV_GIGA) {
		data /= unit;
		conv++;
	}

	/* Fit data in 4 places */
	if (data < 9.995) { /* 9.995 rounded to 10.0 */
		format = "%4.2f %c"; /* #.## */
	} else if (data < 99.95) { /* 99.95 rounded to 100 */
		format = "%4.1f %c"; /* ##.# */
	} else {
		format = "%4.0f %c"; /* #### */
	}
	sprintf(outString, format, data, kLabel[conv]);
}


/** The report function of a TCP server session */
static void udp_conn_report(u64_t diff,
		enum report_type report_type)
{
	u64_t total_len, cnt_datagrams, cnt_dropped_datagrams, total_packets;
	u32_t cnt_out_of_order_datagrams;
	double duration, bandwidth = 0;
	char data[16], perf[16], time[64], drop[64];

	if (report_type == INTER_REPORT) {
		total_len = server.i_report.total_bytes;
		cnt_datagrams = server.i_report.cnt_datagrams;
		cnt_dropped_datagrams = server.i_report.cnt_dropped_datagrams;
	} else {
		server.i_report.last_report_time = 0;
		total_len = server.total_bytes;
		cnt_datagrams = server.cnt_datagrams;
		cnt_dropped_datagrams = server.cnt_dropped_datagrams;
		cnt_out_of_order_datagrams = server.cnt_out_of_order_datagrams;
	}

	total_packets = cnt_datagrams + cnt_dropped_datagrams;
	/* Converting duration from milliseconds to secs,
	 * and bandwidth to bits/sec .
	 */
	duration = diff / 20.0; /* secs */
	if (duration)
		bandwidth = (total_len / duration) * 8.0;

	stats_buffer(data, total_len, BYTES);
	stats_buffer(perf, bandwidth, SPEED);
	/* On 32-bit platforms, xil_printf is not able to print
	 * u64_t values, so converting these values in strings and
	 * displaying results
	 */
	sprintf(time, "%4.1f-%4.1f sec",
			(double)server.i_report.last_report_time,
			(double)(server.i_report.last_report_time + duration));
	sprintf(drop, "%4llu/%5llu (%.2g%%)", cnt_dropped_datagrams,
			total_packets,
			(100.0 * cnt_dropped_datagrams)/total_packets);
	xil_printf("[%3d] %s  %sBytes  %sbits/sec  %s\n\r", server.client_id,
			time, data, perf, drop);

	if (report_type == INTER_REPORT) {
		server.i_report.last_report_time += duration;
	} else if ((report_type != INTER_REPORT) && cnt_out_of_order_datagrams) {
		xil_printf("[%3d] %s  %u datagrams received out-of-order\n\r",
				server.client_id, time,
				cnt_out_of_order_datagrams);
	}
}


static void reset_stats(void)
{
	server.client_id++;
	/* Save start time */
	server.start_time = get_time_ms();
	server.end_time = 0; /* ms */
	server.total_bytes = 0;
	server.cnt_datagrams = 0;
	server.cnt_dropped_datagrams = 0;
	server.cnt_out_of_order_datagrams = 0;
	server.expected_datagram_id = 0;

	/* Initialize Interim report parameters */
	server.i_report.start_time = 0;
	server.i_report.total_bytes = 0;
	server.i_report.cnt_datagrams = 0;
	server.i_report.cnt_dropped_datagrams = 0;
	server.i_report.last_report_time = 0;
}

/** Receive data on a udp session */
static void udp_recv_perf_traffic(void *arg, struct udp_pcb *tpcb,
        struct pbuf *p, const ip_addr_t *addr, u16_t port)
{
    // xil_printf("Received UDP packet\n\r");
    static u8_t first = 1;
    static u64_t now;
    u32_t drop_datagrams = 0;
    s32_t recv_id;

    // xil_printf("Packet length: %d\n\r", p->tot_len);

#ifdef __MICROBLAZE__
    s16_t *payload;
    payload = (s16_t *) (p->payload);
    recv_id = (ntohs(payload[0]) << 16) | ntohs(payload[1]);
#else
    recv_id = ntohl(*((int *)(p->payload)));
#endif
    // xil_printf("Received ID: %d\n\r", recv_id);

    if (first && (recv_id == 1)) {
        // xil_printf("Initializing connection stats\n\r");
        pcb->remote_ip = *addr;
        pcb->remote_port = port;
        reset_stats();
        print_udp_conn_stats();
        first = 0;
    } else if (first) {
        // xil_printf("Ignoring packet: Connection already terminated\n\r");
        return;
    }

    if (recv_id < 0) {
        // xil_printf("Test completion detected\n\r");
        u64_t diff_ms = now - server.start_time;
        udp_sendto(tpcb, p, addr, port);
        udp_conn_report(diff_ms, UDP_DONE_SERVER);
        // xil_printf("UDP test passed Successfully\n\r");
        first = 1;
        pbuf_free(p);
        return;
    }

    if (server.expected_datagram_id != recv_id) {
        if (server.expected_datagram_id < recv_id) {
            drop_datagrams = recv_id - server.expected_datagram_id;
            server.cnt_dropped_datagrams += drop_datagrams;
            server.expected_datagram_id = recv_id + 1;
            // xil_printf("Dropped packets detected: %d\n\r", drop_datagrams);
        } else if (server.expected_datagram_id > recv_id) {
            server.cnt_out_of_order_datagrams++;
            // xil_printf("Out-of-order packet received\n\r");
        }
    } else {
        server.expected_datagram_id++;
    }

    server.cnt_datagrams++;
    server.total_bytes += p->tot_len;
    // // xil_printf("Total received bytes: %llu\n\r", server.total_bytes);

    if (REPORT_INTERVAL_TIME) {
        now = get_time_ms();
        server.i_report.cnt_datagrams++;
        server.i_report.cnt_dropped_datagrams += drop_datagrams;
        server.i_report.total_bytes += p->tot_len;

        if (server.i_report.start_time) {
            u64_t diff_ms = now - server.i_report.start_time;
            if (diff_ms >= REPORT_INTERVAL_TIME) {
                // xil_printf("Generating interim report\n\r");
                udp_conn_report(diff_ms, INTER_REPORT);
                server.i_report.start_time = 0;
                server.i_report.total_bytes = 0;
                server.i_report.cnt_datagrams = 0;
                server.i_report.cnt_dropped_datagrams = 0;
            }
        } else {
            server.i_report.start_time = now;
        }
    }

    pbuf_free(p);
    // xil_printf("Packet processing complete\n\r");
    return;
}

void send_frame()
{
	#define sz (960)
    static char buff[sz];
    static u8_t iteration = 1;
    struct pbuf *p;
    err_t err;
    ip_addr_t dest_ip;

    /* Configurar la dirección IP de destino */
    IP4_ADDR(&dest_ip, 192, 168, 1, 20);

    /* Llenar el buffer con datos de la imagen */
    for (uint16_t i = 0; i < sz; i++) {
        buff[i] = iteration;
    }
    buff[sz - 1] = '\0';  // Asegurar que termina correctamente

    /* Crear un pbuf para enviar los datos */
    p = pbuf_alloc(PBUF_TRANSPORT, sizeof(buff), PBUF_RAM);
    if (!p) {
        xil_printf("Error: No se pudo asignar memoria para el pbuf\r\n");
        return;
    }

    /* Copiar datos al pbuf */
    memcpy(p->payload, buff, sizeof(buff));

    /* Enviar el frame por UDP */
    err = udp_sendto(pcb, p, &dest_ip, pcb->remote_port);
    if (err != ERR_OK) {
        xil_printf("Error enviando frame UDP: %d\r\n", err);
    }

    /* Liberar el pbuf después del envío */
    pbuf_free(p);

    iteration++;
}


void start_application(void)
{
	err_t err;

	/* Create Server PCB */
	pcb = udp_new();
	if (!pcb) {
		xil_printf("UDP server: Error creating PCB. Out of Memory\r\n");
		return;
	}

	err = udp_bind(pcb, IP_ADDR_ANY, UDP_CONN_PORT);
	if (err != ERR_OK) {
		xil_printf("UDP server: Unable to bind to port");
		xil_printf(" %d: err = %d\r\n", UDP_CONN_PORT, err);
		udp_remove(pcb);
		return;
	}

	/* specify callback to use for incoming connections */
	// udp_recv(pcb, udp_recv_perf_traffic, NULL);

	// send_frame();

	return;
}
