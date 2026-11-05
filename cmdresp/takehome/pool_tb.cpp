#include "gen/max_pool.hpp"
#include "include/bundle_tb.h"
#include "trace.hpp"
#include <cstdio>
#include <fstream>
#include <limits>
#include <string>

int main(int argc,char** argv) {
    static_assert(sizeof(float)==4 && std::numeric_limits<float>::is_iec559,"binary32 required");
    if(argc!=3) return 2;
    const std::string root=argv[1],stage=argv[2];
    std::ifstream list(root+"/scenarios.txt");
    std::string name;unsigned runs=0;
    while(list>>name) {
        const std::string dir=root+"/"+name;
        hls::stream<streamutils::axi4s_word<32>> s_in,m_out; // NEW per activation
        ap_uint<1> halted=1;
        ap_uint<8> error=255;
        ap_uint<32> tx_id=0xDEADBEEFu;
        wf::play_stream<32>(dir+"/in",s_in);
        const unsigned initial=s_in.size();
        pool_trace::events().clear();
        std::printf("BEGIN %u %s stage=%s initial=%u\n",runs,name.c_str(),stage.c_str(),initial);
        max_pool(s_in,m_out,halted,error,tx_id); // exactly one call per activation
        const unsigned remaining=s_in.size();
        pool_trace::save(dir+"/"+stage+"/trace.jsonl");
        wf::record_stream<32>(m_out,dir+"/"+stage);
        // Testbench-only snapshot AFTER return; kernel never drains anything.
        wf::record_stream<32>(s_in,dir+"/"+stage+"_unread");
        std::ofstream f(dir+"/"+stage+"/status.json");
        f<<"{\"halted\":"<<unsigned(halted)<<",\"error\":"<<unsigned(error)
          <<",\"tx_id\":"<<unsigned(tx_id)<<",\"consumed\":"<<initial-remaining
          <<",\"remaining\":"<<remaining<<"}\n";
        std::printf("END %s halted=%u error=%u tx=%u consumed=%u unread=%u\n",name.c_str(),
                    unsigned(halted),unsigned(error),unsigned(tx_id),initial-remaining,remaining);
        ++runs;
    }
    std::printf("RECORDED %u activations (all scenarios; fresh streams every call)\n",runs);
    return runs?0:1;
}
