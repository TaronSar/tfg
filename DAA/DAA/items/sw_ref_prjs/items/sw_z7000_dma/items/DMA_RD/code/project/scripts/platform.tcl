proc create_platform {xsa_file} {
    setws ../../
    platform create -name "platform" -hw $xsa_file -arch 32-bit -os standalone -out ../../
    domain create -name domain_ps7_cortexa9_0 -os standalone -proc ps7_cortexa9_0 -arch 32-bit
    platform generate
}