#pragma once
#include "include/cmd_hdr.h"
#include "include/resp_hdr.h"
#include "include/float32_array_utils.h"
#include "trace.hpp"

namespace scale_offset_impl {
enum ErrorCode { NONE=0, BAD_HEADER=1, BAD_COMMAND=2, BAD_PARAM=3,
                 NOT_CONFIGURED=4, EARLY_TLAST=5, MISSING_TLAST=6 };
enum Opcode { CONFIG=1, DATA=2, END=3 };

static inline float evaluate(float a, float b, float x) {
    // Both stores round to binary32. Compile with -ffp-contract=off and
    // -fno-fast-math as recorded in run.tcl. No numeric-domain checks.
    volatile float product = a * x;
    volatile float result = product + b;
    return result;
}

template<int in_bw, int out_bw>
void body(hls::stream<streamutils::axi4s_word<in_bw>>& s_in,
          hls::stream<streamutils::axi4s_word<out_bw>>& m_out,
          ap_uint<1>& halted, ap_uint<8>& error, ap_uint<32>& tx_id) {
#pragma HLS INLINE
    static_assert(in_bw == 32 && out_bw == 32, "This protocol is fixed at 32 bits");
    halted = 0; error = NONE; tx_id = 0;
    bool configured = false;
    float a = 0.0f, b = 0.0f;
    SO_EVENT("START", 0, 0);
    while (true) {
        ap_uint<32> raw[6] = {};
        CmdHdr h;
        ap_uint<32> current_id = 0xFFFFFFFFu;
        // Inspect framing on each received word: no reading past an early
        // header violation. Schema decoding is used even for partial headers.
        for (unsigned j=0; j<6; ++j) {
            const auto word = s_in.read();  // blocking; deliberately no timeout
            raw[j] = word.data;
            h.read_array<32>(raw);
            if (j >= 1) current_id = h.tx_id;
            SO_EVENT("HREAD", current_id, j+1);
            if ((j == 0 && h.magic != 0x53434F46u) || bool(word.last) != (j == 5)) {
                halted = 1; error = BAD_HEADER; tx_id = current_id;
                SO_EVENT("ERROR", current_id, BAD_HEADER);
                return;
            }
        }
        if (h.opcode != CONFIG && h.opcode != DATA && h.opcode != END) {
            halted = 1; error = BAD_COMMAND; tx_id = current_id;
            SO_EVENT("ERROR", current_id, BAD_COMMAND);
            return;
        }
        if ((h.opcode == DATA && h.nsamp == 0) || (h.opcode != DATA && h.nsamp != 0)) {
            halted = 1; error = BAD_PARAM; tx_id = current_id;
            SO_EVENT("ERROR", current_id, BAD_PARAM);
            return;
        }
        if (h.opcode == END) {
            SO_EVENT("END", current_id, 0);
            return;
        }
        if (h.opcode == CONFIG) {
            a = h.a; b = h.b; configured = true;
        } else if (!configured) {
            halted = 1; error = NOT_CONFIGURED; tx_id = current_id;
            SO_EVENT("ERROR", current_id, NOT_CONFIGURED);
            return;
        }
        RespHdr response;
        response.opcode = h.opcode;
        response.tx_id = current_id;
        response.write_axi4_stream<32>(m_out, true);
        SO_EVENT("RESP_DONE", current_id, h.opcode);
        if (h.opcode == CONFIG) continue;

        bool pending = false;
        float held[1] = {};
        // Keep one valid result untransferred until the next sample is checked.
        // This makes its TLAST decidable without ever rewriting a sent word.
        for (ap_uint<32> i=0; i<h.nsamp; ++i) {
            float input[1];
            streamutils::tlast_status tl = streamutils::tlast_status::no_tlast;
            float32_array_utils::read_axi4_stream_lane<32>(s_in, input, 1, tl);
            const bool last = tl == streamutils::tlast_status::tlast_at_end;
            const bool final = (i == h.nsamp-1);
            SO_EVENT("PREAD", current_id, i+1);
            if (last != final) {
                halted = 1; error = last ? EARLY_TLAST : MISSING_TLAST; tx_id = current_id;
                SO_EVENT("ERROR", current_id, error);
                if (pending) {
                    float32_array_utils::write_axi4_stream_lane<32>(held, m_out, true, 1);
                    SO_EVENT("FLUSH", current_id, i);
                }
                return; // no more reads; offending input is never evaluated or emitted
            }
            if (pending) {
                float32_array_utils::write_axi4_stream_lane<32>(held, m_out, false, 1);
                SO_EVENT("RESULT", current_id, i);
            }
            held[0] = evaluate(a, b, input[0]);
            pending = true;
            if (final) {
                float32_array_utils::write_axi4_stream_lane<32>(held, m_out, true, 1);
                SO_EVENT("RESULT_LAST", current_id, i+1);
            }
        }
    }
}
} // namespace scale_offset_impl
