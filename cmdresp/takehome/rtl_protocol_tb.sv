`timescale 1ns/1ps
// Hand-written AXI host. Complete fixtures remain offered through error/END.
// The pending word is cancelled only WITH reset, after done/status/observation.
module rtl_protocol_tb;
  reg clk=0;
  always #5 clk=~clk;
  reg resetn=0, active=0;
  reg [31:0] s_in_TDATA=0;
  reg s_in_TVALID=0, s_in_TLAST=0;
  wire s_in_TREADY;
  wire [31:0] m_out_TDATA;
  wire m_out_TVALID,m_out_TLAST;
  reg m_out_TREADY=1;
  reg awvalid=0,wvalid=0,arvalid=0;
  reg [5:0] awaddr=0,araddr=0;
  reg [31:0] wdata=0;
  wire awready,wready,bvalid,arready,rvalid,interrupt;
  wire [1:0] bresp,rresp;
  wire [31:0] rdata;
  wire [3:0] outkeep,outstrb;
  max_pool dut(.ap_clk(clk),.ap_rst_n(resetn),
    .s_in_TDATA(s_in_TDATA),.s_in_TVALID(s_in_TVALID),.s_in_TREADY(s_in_TREADY),
    .s_in_TLAST(s_in_TLAST),.s_in_TKEEP(4'hf),.s_in_TSTRB(4'hf),
    .m_out_TDATA(m_out_TDATA),.m_out_TVALID(m_out_TVALID),.m_out_TREADY(m_out_TREADY),
    .m_out_TLAST(m_out_TLAST),.m_out_TKEEP(outkeep),.m_out_TSTRB(outstrb),
    .s_axi_control_AWVALID(awvalid),.s_axi_control_AWREADY(awready),.s_axi_control_AWADDR(awaddr),
    .s_axi_control_WVALID(wvalid),.s_axi_control_WREADY(wready),.s_axi_control_WDATA(wdata),
    .s_axi_control_WSTRB(4'hf),.s_axi_control_BVALID(bvalid),.s_axi_control_BREADY(1'b1),.s_axi_control_BRESP(bresp),
    .s_axi_control_ARVALID(arvalid),.s_axi_control_ARREADY(arready),.s_axi_control_ARADDR(araddr),
    .s_axi_control_RVALID(rvalid),.s_axi_control_RREADY(1'b1),.s_axi_control_RDATA(rdata),.s_axi_control_RRESP(rresp),
    .interrupt(interrupt));

  reg [31:0] input_data[0:32767],expected_data[0:32767];
  integer input_last[0:32767],expected_last[0:32767];
  integer input_requirement[0:32767],output_requirement[0:32767];
  integer input_cycle[0:32767],output_cycle[0:32767];
  integer cycle=0,case_index=-1,in_count=0,out_count=0;
  integer full_count,stop_count,expected_count,expected_halted,expected_error,bp_mode;
  reg [31:0] expected_tx;
  integer failures=0,total_failures=0,bp_left=0,bp_cycles=0,done_cycle=-1;
  integer events,summary,listfile,inf,outf,rc,j,watch;
  integer bcount=0;
  string fixture_root,output_root,name;
  reg [31:0] control_value,actual_halted,actual_error,actual_tx;

  // Drive away from the sampling edge. Do not pause at expected stop_count.
  always @(negedge clk) begin
    if(!resetn || !active) begin
      s_in_TVALID=0;m_out_TREADY=1;
    end else begin
      s_in_TVALID=(in_count<full_count);
      if(in_count<full_count) begin
        s_in_TDATA=input_data[in_count];s_in_TLAST=input_last[in_count];
      end
      if(bp_mode!=0 && out_count==2 && bp_left>0) begin
        m_out_TREADY=0;bp_left=bp_left-1;
      end else m_out_TREADY=1;
    end
  end

  // External pins only. C shadow stream sizes are not used by this monitor.
  always @(posedge clk) begin
    cycle=cycle+1;
    if(resetn && bvalid) bcount=bcount+1;
    if(active && resetn) begin
      if(bp_mode!=0 && out_count==2 && !m_out_TREADY) bp_cycles=bp_cycles+1;
      if(dut.ap_done && done_cycle<0) done_cycle=cycle;
      if(s_in_TVALID && s_in_TREADY) begin
        $fdisplay(events,"%0d input %0d %0d %08x %0d",case_index,cycle,in_count,s_in_TDATA,s_in_TLAST);
        input_cycle[in_count]=cycle;
        if(in_count>=stop_count) begin
          failures=failures+1;$display("FAIL %s extra input handshake index=%0d cycle=%0d",name,in_count,cycle);
        end
        if(input_requirement[in_count]>=0) begin
          if(out_count<=input_requirement[in_count] || output_cycle[input_requirement[in_count]]>=cycle) begin
            failures=failures+1;$display("FAIL %s payload before complete response cycle=%0d",name,cycle);
          end
        end
        in_count=in_count+1;
      end
      if(m_out_TVALID && m_out_TREADY) begin
        $fdisplay(events,"%0d output %0d %0d %08x %0d",case_index,cycle,out_count,m_out_TDATA,m_out_TLAST);
        output_cycle[out_count]=cycle;
        if(out_count>=expected_count) begin
          failures=failures+1;$display("FAIL %s extra output",name);
        end else begin
          if(m_out_TDATA!==expected_data[out_count] || m_out_TLAST!==expected_last[out_count][0]) begin
            failures=failures+1;$display("FAIL %s output mismatch index=%0d",name,out_count);
          end
          if(output_requirement[out_count]>=0 && (in_count<=output_requirement[out_count] || input_cycle[output_requirement[out_count]]>=cycle)) begin
            failures=failures+1;$display("FAIL %s result before complete input",name);
          end
        end
        out_count=out_count+1;
      end
    end
  end

  task automatic axi_write(input reg [5:0] address,input reg [31:0] value);
    integer old_bcount;
    begin
      old_bcount=bcount;
      @(negedge clk);awaddr=address;wdata=value;awvalid=1;wvalid=1;
      fork
        begin do @(posedge clk);while(!awready);@(negedge clk);awvalid=0;end
        begin do @(posedge clk);while(!wready);@(negedge clk);wvalid=0;end
      join
      wait(bcount>old_bcount);
    end
  endtask
  task automatic axi_read(input reg [5:0] address,output reg [31:0] value);
    begin
      @(negedge clk);araddr=address;arvalid=1;
      do @(posedge clk);while(!arready);
      @(negedge clk);arvalid=0;
      do @(posedge clk);while(!rvalid);
      value=rdata;
      if(rresp!=0) failures=failures+1;
    end
  endtask

  initial begin
    if(!$value$plusargs("FIXTURE_ROOT=%s",fixture_root)) $fatal(1,"No fixture root");
    if(!$value$plusargs("OUTPUT_ROOT=%s",output_root)) $fatal(1,"No output root");
    events=$fopen({output_root,"/handshakes.txt"},"w");
    summary=$fopen({output_root,"/summary.txt"},"w");
    listfile=$fopen({fixture_root,"/cases.txt"},"r");
    if(!events || !summary || !listfile) $fatal(1,"Cannot open test files");
    while(!$feof(listfile)) begin
      rc=$fscanf(listfile,"%s %d %d %d %d %d %h %d\n",name,full_count,stop_count,expected_count,expected_halted,expected_error,expected_tx,bp_mode);
      if(rc==8) begin
        case_index=case_index+1;
        @(negedge clk);active=0;resetn=0;awvalid=0;wvalid=0;arvalid=0;
        repeat(5) @(negedge clk);
        in_count=0;out_count=0;failures=0;bp_left=12;bp_cycles=0;done_cycle=-1;bcount=0;
        for(j=0;j<32768;j=j+1) begin input_cycle[j]=-1;output_cycle[j]=-1;end
        inf=$fopen({fixture_root,"/",name,".in"},"r");
        outf=$fopen({fixture_root,"/",name,".out"},"r");
        if(!inf || !outf) $fatal(1,"Cannot open case");
        for(j=0;j<full_count;j=j+1) begin
          rc=$fscanf(inf,"%h %d %d\n",input_data[j],input_last[j],input_requirement[j]);
          if(rc!=3) $fatal(1,"Bad input fixture");
        end
        for(j=0;j<expected_count;j=j+1) begin
          rc=$fscanf(outf,"%h %d %d\n",expected_data[j],expected_last[j],output_requirement[j]);
          if(rc!=3) $fatal(1,"Bad output fixture");
        end
        $fclose(inf);$fclose(outf);
        @(negedge clk);resetn=1;
        repeat(3) @(negedge clk);
        active=1;
        $display("PROTOCOL BEGIN %0d %s offered=%0d stop=%0d",case_index,name,full_count,stop_count);
        fork
          begin
            axi_write(0,1);
            control_value=0;
            while(!control_value[1]) axi_read(0,control_value);
            axi_read(6'h10,actual_halted);axi_read(6'h20,actual_error);axi_read(6'h30,actual_tx);
          end
          begin
            repeat(1000000) @(posedge clk);
            $fatal(1,"Harness watchdog: kernel did not complete %s (not a kernel timeout)",name);
          end
        join_any
        disable fork;
        // Keep the next pending word valid through status reads AND observation.
        // Status read finishes at a rising edge: 17 falling-edge waits give
        // 16 COMPLETE subsequent rising-edge observations before reset.
        repeat(17) @(negedge clk);
        if(in_count!=stop_count || out_count!=expected_count || actual_halted!=expected_halted || actual_error!=expected_error || actual_tx!=expected_tx) failures=failures+1;
        if(full_count>stop_count && (!s_in_TVALID || s_in_TDATA!==input_data[stop_count] || s_in_TLAST!==input_last[stop_count][0])) failures=failures+1;
        if(bp_mode!=0 && bp_cycles<12) failures=failures+1;
        $fdisplay(summary,"%0d %s %0d %0d %0d %0d %0d %0d %08x %0d %0d %0d %0d",case_index,name,full_count,stop_count,in_count,expected_count,out_count,actual_error,actual_tx,failures,bp_cycles,done_cycle,cycle);
        $display("PROTOCOL END %s failures=%0d received=%0d remaining=%0d outputs=%0d bp=%0d",name,failures,in_count,full_count-in_count,out_count,bp_cycles);
        total_failures=total_failures+failures;
        // AXI allows cancellation of the still-valid beat only when reset occurs.
        resetn=0;active=0;
      end
    end
    $fclose(events);$fclose(summary);$fclose(listfile);
    if(case_index!=68 || total_failures!=0) $fatal(1,"PROTOCOL FAIL cases=%0d failures=%0d",case_index+1,total_failures);
    $display("PROTOCOL ALL PASS: %0d activations with complete fixtures",case_index+1);
    $finish;
  end
endmodule
