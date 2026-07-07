proc create_platform {xsa_file project_name psw_target} {
    setws ../../

    platform create -name $project_name -hw $xsa_file -arch 64-bit -os standalone -out ../../
    domain create -name domain_${psw_target} -os standalone -proc $psw_target -arch 64-bit

    platform generate
}

# Recompila la plataforma ya creada
proc rebuild_platform {project_name} {
    setws ../../
    platform active $project_name
    platform generate
}
