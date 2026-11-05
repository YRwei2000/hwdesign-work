# Correctness revision: source/fixtures unchanged, isolated HLS project.
set root [file dirname [file normalize [info script]]]
cd $root
if {![info exists ::env(POOL_FIX_STAGE)] || $::env(POOL_FIX_STAGE) ni {synth cosim_setup}} {
    error "Set POOL_FIX_STAGE=synth or cosim_setup"
}
set stage $::env(POOL_FIX_STAGE)
if {$stage eq "synth"} {
    open_project -reset off_proj
    set_top max_pool
    set flags "-I$root -std=c++14 -fno-fast-math"
    add_files [file join $root gen_off max_pool.cpp] -cflags $flags
    add_files -tb [file join $root pool_tb.cpp] -cflags $flags
    open_solution -reset solution1
    set_part {xc7z020clg484-1}
    create_clock -period 10
    set_directive_interface -mode axis -register_mode off max_pool s_in
    set_directive_interface -mode axis -register_mode off max_pool m_out
    puts "POOL_FIX_REQUEST s_in=off m_out=off"
    csim_design -clean -argv "[file join $root data] csim_fix"
    csynth_design
} else {
    open_project off_proj
    open_solution solution1
    cosim_design -setup -rtl verilog -trace_level port -argv "[file join $root data] cosim_fix"
}
puts "POOL_FIX_STAGE_COMPLETED $stage"
exit 0
