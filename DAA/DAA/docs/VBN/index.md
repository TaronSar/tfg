# Estructura de directorios para la documentación de DAA

```
embention/DAA/
    |-- README.md: descripción global del repo y link a documentación
    |-- /docs
        |-- README.md: índice documentación
        |-- /VBN_platform_MVP: plataforma Video Based Navigation para el MVP
            |-- VBN_platform.md: descripción general arquitectura Hw/Sw VBN
            |-- HW_stack.md: descripción de la parte PL/PS
                -> /fpga_orb: Vivado prj
            |-- SW_stack.md: descripción de las capas Sw
                -> /sw_gnssdenied: App vbn + libs
                -> /sw_orb: drivers linux IPs
                -> /sw_plnx: Petalinux
                -> /sw_zusp: drivers baremetal IPs
                -> /sw_ref_prjs: proyectos referencia baremetal
            |-- /analisis_docs: pdfs de análisis
            |-- /img: archivos de imágenes
        |-- /VBN_platform_v2:
        | ...
        | ...

        |-- /RadarAlt_platform: plataforma para Radar-Altímetro
            |-- RadarAlt_Platform.md: descripción general arquitectura Hw/Sw RadAlt
            |-- Hw_stack.md
                -> directorios relacionados
            |-- Sw-stack.md
                -> directorios relacionados
        |-- ....
```