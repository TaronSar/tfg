
file "../cmake/build/vbn_standalone.elf"
target extended-remote localhost:3001
#Add core 1 to debugger
add-inferior -exec "../cmake/build/vbn_standalone.elf"
inferior 2
attach 2
#Come back to core 0
inferior 1
tui enable
layout split