proc create_platform {xsa_file} {
    setws ../../
    platform create -name "platform" -hw $xsa_file -arch 64-bit -os standalone -out ../../
    domain create -name domain_psu_cortexa53_0 -os standalone -proc psu_cortexa53_0 -arch 64-bit
    platform generate
}