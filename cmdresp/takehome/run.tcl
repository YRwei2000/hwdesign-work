# Explicit stages: first cosim always invokes the full scenarios.txt testbench.
set root [file dirname [file normalize [info script]]]
cd $root
if {![info exists ::env(POOL_STAGE)] || $::env(POOL_STAGE) ni {csim synth cosim}} {
    error "Set POOL_STAGE to csim, synth or cosim"
}
set stage $::env(POOL_STAGE)
if {$stage eq "csim"} {
    open_project -reset pool_proj
    set_top max_pool
    set flags "-I$root -std=c++14 -fno-fast-math"
    puts "POOL_CFLAGS $flags"
    add_files [file join $root gen max_pool.cpp] -cflags $flags
    add_files -tb [file join $root pool_tb.cpp] -cflags $flags
    open_solution -reset solution1
    set_part {xc7z020clg484-1}
    create_clock -period 10
    csim_design -clean -argv "[file join $root data] csim"
} else {
    open_project pool_proj
    open_solution solution1
    if {$stage eq "synth"} {
        csynth_design
    } else {
        # Port waveform is the evidence for handshakes, ordering and measured cycles.
        cosim_design -rtl verilog -trace_level port -argv "[file join $root data] cosim"
    }
}
puts "POOL_STAGE_COMPLETED $stage"
exit 0
