#include <stdio.h>
#include <stdlib.h>
#include <fcntl.h>
#include <sys/mman.h>
#include <unistd.h>

// Dirección base y tamaño del mapeo
#define IP_BASE_ADDR 0xB0010000
#define MAP_SIZE 4096 // Mapeamos 4KB, suficiente para cubrir todos los registros

// Offsets de los registros (en bytes)
#define NPIX_OFFSET   0x10
#define SUMVAL_OFFSET 0x14
#define ROWS_OFFSET   0x30
#define COLS_OFFSET   0x38
#define HISTO_OFFSET  0x400

int main() {
    int fd;
    void *map_base;
    volatile unsigned int *ip_ptr; // Puntero a la memoria del IP

    // 1. Abrir el dispositivo de memoria
    if ((fd = open("/dev/mem", O_RDWR | O_SYNC)) == -1) {
        perror("Error abriendo /dev/mem");
        return -1;
    }

    // 2. Mapear la memoria física del IP a la memoria virtual
    map_base = mmap(0, MAP_SIZE, PROT_READ | PROT_WRITE, MAP_SHARED, fd, IP_BASE_ADDR);
    if (map_base == MAP_FAILED) {
        perror("Error en mmap");
        close(fd);
        return -1;
    }

    // Puntero para acceder a los registros como un array de enteros de 32 bits
    ip_ptr = (volatile unsigned int *)map_base;

    // --- AHORA PUEDES LEER Y ESCRIBIR ---

    // Escribir en los registros de configuración (ej: 1920x1080)
    // Dividimos por 4 porque el puntero es de tipo int (4 bytes)
    printf("Configurando Rows=1080 y Cols=1920...\n");
    ip_ptr[ROWS_OFFSET / 4] = 1080;
    ip_ptr[COLS_OFFSET / 4] = 1920;

    // Pequeña pausa para que el IP procese algo (si es necesario)
    usleep(100000); 

    // Leer los registros de estado
    unsigned int npix = ip_ptr[NPIX_OFFSET / 4];
    unsigned int sumval = ip_ptr[SUMVAL_OFFSET / 4];
    printf("Lectura de registros:\n");
    printf("  Npix   = %u (0x%X)\n", npix, npix);
    printf("  SumVal = %u (0x%X)\n", sumval, sumval);
    
    // Leer los primeros 10 valores del histograma
    printf("Primeros 10 valores del histograma:\n");
    for (int i = 0; i < 256; i++) {
        unsigned int histo_val = ip_ptr[(HISTO_OFFSET / 4) + i];
        printf("  Histo[%d] = %u\n", i, histo_val);
    }
    
    // 3. Liberar recursos
    if (munmap(map_base, MAP_SIZE) == -1) {
        perror("Error en munmap");
    }
    close(fd);

    return 0;
}