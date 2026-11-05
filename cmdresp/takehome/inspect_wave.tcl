# Offline inspection only: never launches or reruns a simulation.
open_wave_database pool_proj/solution1/sim/verilog/max_pool.wdb
puts "DATABASE [current_sim]"
puts "WAVE_COMMANDS [info commands *wave*]"
puts "RDI_WAVE_COMMANDS [info commands ::rdi::*wave*]"
puts "RDI_DATA_COMMANDS [info commands ::rdi::*data*]"
foreach command {{report_property [lindex [get_waves -r *s_in_TVALID*] 0]}
                 {help add_wave_virtual_bus}
                 {find_next_wave_value -wave [lindex [get_waves -r *s_in_TVALID*] 0] -time 0ns 1}
                 {find_next_wave_value -wave [lindex [get_waves -r *s_in_TREADY*] 0] -time 0ns 1}
                 {info commands ::*::*wave*}} {
    set rc [catch {eval $command} message]
    puts "COMMAND $command RC $rc RESULT $message"
}
exit
