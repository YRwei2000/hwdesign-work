open_vcd /home/yw9286/hwdesign-work/cmdresp/takehome/evidence/fix_v2/protocol/protocol.vcd
log_vcd [get_objects -filter {type == in_port || type == out_port || type == inout_port || type == port} /rtl_protocol_tb/dut/*]
log_vcd [get_objects /rtl_protocol_tb/case_index]
log_vcd [get_objects /rtl_protocol_tb/active]
run all
close_vcd
quit
