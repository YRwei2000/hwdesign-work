#pragma once
#include "include/pool_cmd.h"
#include "include/pool_resp.h"
#include "include/float32_array_utils.h"
#include "trace.hpp"

namespace pool_impl {
enum Code { NONE=0, HEADER=1, COMMAND=2, H_RANGE=3, W_RANGE=4, K_RANGE=5,
            WINDOW=6, DIVISIBILITY=7, EARLY_TLAST=8, MISSING_TLAST=9 };
static inline unsigned parameter_error(unsigned h,unsigned w,unsigned k) {
#pragma HLS INLINE
    if(h<1 || h>64) return H_RANGE;
    if(w<1 || w>64) return W_RANGE;
    if(k<1 || k>8) return K_RANGE;
    if(k>h || k>w) return WINDOW;
    if(h%k || w%k) return DIVISIBILITY;
    return NONE;
}
template<int in_bw,int out_bw>
void body(hls::stream<streamutils::axi4s_word<in_bw>>& s_in,
          hls::stream<streamutils::axi4s_word<out_bw>>& m_out,
          ap_uint<1>& halted,ap_uint<8>& error,ap_uint<32>& tx_id) {
#pragma HLS INLINE
    static_assert(in_bw==32 && out_bw==32,"32-bit streams required");
    halted=0;error=0;tx_id=0;
    float matrix[4096];
    float results[4096];
    POOL_EVENT("START",0,0);
    command_loop: while(true) {
        ap_uint<32> raw[6]={};
        PoolCmd h;
        ap_uint<32> id=0xFFFFFFFFu;
        header_loop: for(unsigned j=0;j<6;++j) {
            const auto word=s_in.read(); // blocking: no empty test or timeout
            raw[j]=word.data;
            h.read_array<32>(raw); // generated schema decoder, including partial headers
            if(j>=1) id=h.tx_id;
            POOL_EVENT("HREAD",id,j+1);
            if((j==0 && h.magic!=0x504F4F4Cu) || bool(word.last)!=(j==5)) {
                halted=1;error=HEADER;tx_id=id;
                POOL_EVENT("ERROR",id,HEADER);
                return;
            }
        }
        if(h.opcode!=1 && h.opcode!=2) {
            halted=1;error=COMMAND;tx_id=id;POOL_EVENT("ERROR",id,COMMAND);return;
        }
        if(h.opcode==2) { POOL_EVENT("END",id,0);return; }
        const unsigned height=h.h,width=h.w,k=h.k;
        const unsigned pe=parameter_error(height,width,k);
        if(pe) { halted=1;error=pe;tx_id=id;POOL_EVENT("ERROR",id,pe);return; }
        const unsigned count=height*width,oh=height/k,ow=width/k;
        PoolResp resp;resp.tx_id=id;resp.out_h=oh;resp.out_w=ow;
        resp.write_axi4_stream<32>(m_out,true);
        POOL_EVENT("RESP_DONE",id,0);
        receive_loop: for(unsigned i=0;i<count;++i) {
#pragma HLS PIPELINE II=1
#pragma HLS LOOP_TRIPCOUNT min=1 max=4096
            float value[1];
            streamutils::tlast_status tl=streamutils::tlast_status::no_tlast;
            float32_array_utils::read_axi4_stream_lane<32>(s_in,value,1,tl);
            const bool last=(tl==streamutils::tlast_status::tlast_at_end);
            POOL_EVENT("PREAD",id,i+1);
            if(last!=(i==count-1)) {
                halted=1;error=last?EARLY_TLAST:MISSING_TLAST;tx_id=id;
                POOL_EVENT("ERROR",id,error);
                return; // no result burst started, all local matrix/results discarded
            }
            matrix[i]=value[0];
        }
        POOL_EVENT("INPUT_VALID",id,count);
        pool_rows: for(unsigned r=0;r<oh;++r) {
#pragma HLS LOOP_TRIPCOUNT min=1 max=64
            pool_columns: for(unsigned c=0;c<ow;++c) {
#pragma HLS LOOP_TRIPCOUNT min=1 max=64
                float best=matrix[(r*k)*width+c*k];
                window_rows: for(unsigned dr=0;dr<k;++dr) {
#pragma HLS LOOP_TRIPCOUNT min=1 max=8
                    window_columns: for(unsigned dc=0;dc<k;++dc) {
#pragma HLS LOOP_TRIPCOUNT min=1 max=8
                        const float candidate=matrix[(r*k+dr)*width+c*k+dc];
                        if(candidate>best) best=candidate;
                    }
                }
                results[r*ow+c]=best;
            }
        }
        const unsigned nout=oh*ow;
        emit_loop: for(unsigned i=0;i<nout;++i) {
#pragma HLS PIPELINE II=1
#pragma HLS LOOP_TRIPCOUNT min=1 max=4096
            float lane[1]={results[i]};
            float32_array_utils::write_axi4_stream_lane<32>(lane,m_out,i==nout-1,1);
            POOL_EVENT("RESULT",id,i+1);
        }
    }
}
} // namespace pool_impl
