#include "gen/scale_offset.hpp"
#include "include/bundle_tb.h"
#include "trace.hpp"
#include <cfenv>
#include <cstdio>
#include <fstream>
#include <limits>
#include <string>

int main(int argc, char** argv) {
    static_assert(sizeof(float) == 4 && std::numeric_limits<float>::is_iec559,
                  "IEEE binary32 float required");
    if (argc != 2 || std::fesetround(FE_TONEAREST) != 0 || std::fegetround() != FE_TONEAREST)
        return 2;
    const std::string root = argv[1];
    std::ifstream list(root + "/scenarios.txt");
    std::string name;
    unsigned run = 0;
    while (list >> name) {
        const std::string dir = root + "/" + name;
        // New objects per activation: destruction, not draining/reuse, models reset.
        hls::stream<streamutils::axi4s_word<32>> s_in, m_out;
        ap_uint<1> halted = 1;
        ap_uint<8> error = 255;
        ap_uint<32> tx_id = 0xDEADBEEFu;
        wf::play_stream<32>(dir + "/in", s_in);
        const unsigned initial = s_in.size();
        scale_offset_trace::events().clear();
        scale_offset(s_in, m_out, halted, error, tx_id);
        const unsigned remaining = s_in.size();
        scale_offset_trace::save(dir + "/csim/trace.jsonl");
        wf::record_stream<32>(m_out, dir + "/csim");
        // Snapshot unread words AFTER the kernel returned, solely as evidence.
        // These objects are destroyed at iteration end and never reused.
        wf::record_stream<32>(s_in, dir + "/unread");
        std::ofstream st(dir + "/csim/status.json");
        st << "{\"halted\":" << unsigned(halted) << ",\"error\":" << unsigned(error)
           << ",\"tx_id\":" << unsigned(tx_id) << ",\"consumed\":" << initial-remaining
           << ",\"remaining\":" << remaining << "}\n";
        std::printf("%s halted=%u error=%u tx_id=%u consumed=%u unread=%u\n", name.c_str(),
                    unsigned(halted), unsigned(error), unsigned(tx_id), initial-remaining, remaining);
        ++run;
    }
    std::printf("RECORDED %u fresh-stream activations; FE_TONEAREST=%d\n", run, std::fegetround());
    return run ? 0 : 1;
}
