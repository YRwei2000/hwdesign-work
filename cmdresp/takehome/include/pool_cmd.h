#ifndef INCLUDE_POOL_CMD_H
#define INCLUDE_POOL_CMD_H

#include <ap_int.h>
#include <hls_stream.h>
#if __has_include(<hls_axi_stream.h>)
#include <hls_axi_stream.h>
#else
#include <ap_axi_sdata.h>
#endif
#include "streamutils_hls.h"

struct PoolCmd {
    ap_uint<32> magic;
    ap_uint<32> tx_id;
    ap_uint<32> opcode;
    ap_uint<32> h;
    ap_uint<32> w;
    ap_uint<32> k;

    static constexpr int bitwidth = 192;

    template<int word_bw>
    struct word_bw_tag {};

    template<int word_bw>
    static constexpr int nwords_value(word_bw_tag<word_bw>) {
            static_assert(word_bw < 0, "Unsupported word_bw for nwords");
            return 0;
    }

    static constexpr int nwords_value(word_bw_tag<32>) {
            return 6;
    }

    template<int word_bw>
    static constexpr int nwords() {
        return nwords_value(word_bw_tag<word_bw>{});
    }

    static ap_uint<bitwidth> pack_to_uint(const PoolCmd& data) {
        ap_uint<bitwidth> res = 0;
        res.range(31, 0) = data.magic;
        res.range(63, 32) = data.tx_id;
        res.range(95, 64) = data.opcode;
        res.range(127, 96) = data.h;
        res.range(159, 128) = data.w;
        res.range(191, 160) = data.k;
        return res;
    }

    static PoolCmd unpack_from_uint(const ap_uint<bitwidth>& packed) {
        PoolCmd data;
        data.magic = (ap_uint<32>)(packed.range(31, 0));
        data.tx_id = (ap_uint<32>)(packed.range(63, 32));
        data.opcode = (ap_uint<32>)(packed.range(95, 64));
        data.h = (ap_uint<32>)(packed.range(127, 96));
        data.w = (ap_uint<32>)(packed.range(159, 128));
        data.k = (ap_uint<32>)(packed.range(191, 160));
        return data;
    }

    template<int word_bw>
    static void write_array_impl(word_bw_tag<word_bw>, const PoolCmd* self, ap_uint<word_bw> x[]) {
        static_assert(word_bw < 0, "Unsupported word_bw for write_array");
        (void)self;
        (void)x;
    }

    static void write_array_impl(word_bw_tag<32>, const PoolCmd* self, ap_uint<32> x[]) {
        x[0] = self->magic;
        x[1] = self->tx_id;
        x[2] = self->opcode;
        x[3] = self->h;
        x[4] = self->w;
        x[5] = self->k;
    }

    template<int word_bw>
    void write_array(ap_uint<word_bw> x[]) const {
        write_array_impl(word_bw_tag<word_bw>{}, this, x);
    }

    template<int word_bw>
    static void write_stream_impl(word_bw_tag<word_bw>, const PoolCmd* self, hls::stream<ap_uint<word_bw>> &s) {
        static_assert(word_bw < 0, "Unsupported word_bw for write_stream");
        (void)self;
        (void)s;
    }

    static void write_stream_impl(word_bw_tag<32>, const PoolCmd* self, hls::stream<ap_uint<32>> &s) {
            ap_uint<32> w = 0;
        w = self->magic;
        s.write(w);
        w = 0;
        w = self->tx_id;
        s.write(w);
        w = 0;
        w = self->opcode;
        s.write(w);
        w = 0;
        w = self->h;
        s.write(w);
        w = 0;
        w = self->w;
        s.write(w);
        w = 0;
        w = self->k;
        s.write(w);
        w = 0;
    }

    template<int word_bw>
    void write_stream(hls::stream<ap_uint<word_bw>> &s) const {
        write_stream_impl(word_bw_tag<word_bw>{}, this, s);
    }

    template<int word_bw>
    static void write_axi4_stream_impl(word_bw_tag<word_bw>, const PoolCmd* self, hls::stream<streamutils::axi4s_word<word_bw>> &s, bool tlast) {
        static_assert(word_bw < 0, "Unsupported word_bw for write_axi4_stream");
        (void)self;
        (void)s;
        (void)tlast;
    }

    static void write_axi4_stream_impl(word_bw_tag<32>, const PoolCmd* self, hls::stream<streamutils::axi4s_word<32>> &s, bool tlast) {
            ap_uint<32> w = 0;
        w = self->magic;
        streamutils::write_axi4_word<32>(s, w, false);
        w = 0;
        w = self->tx_id;
        streamutils::write_axi4_word<32>(s, w, false);
        w = 0;
        w = self->opcode;
        streamutils::write_axi4_word<32>(s, w, false);
        w = 0;
        w = self->h;
        streamutils::write_axi4_word<32>(s, w, false);
        w = 0;
        w = self->w;
        streamutils::write_axi4_word<32>(s, w, false);
        w = 0;
        w = self->k;
        streamutils::write_axi4_word<32>(s, w, tlast);
        w = 0;
    }

    template<int word_bw>
    void write_axi4_stream(hls::stream<streamutils::axi4s_word<word_bw>> &s, bool tlast = true) const {
        write_axi4_stream_impl(word_bw_tag<word_bw>{}, this, s, tlast);
    }

    template<int word_bw>
    static void read_array_impl(word_bw_tag<word_bw>, PoolCmd* self, const ap_uint<word_bw> x[]) {
        static_assert(word_bw < 0, "Unsupported word_bw for read_array");
        (void)self;
        (void)x;
    }

    static void read_array_impl(word_bw_tag<32>, PoolCmd* self, const ap_uint<32> x[]) {
        self->magic = (ap_uint<32>)(x[0]);
        self->tx_id = (ap_uint<32>)(x[1]);
        self->opcode = (ap_uint<32>)(x[2]);
        self->h = (ap_uint<32>)(x[3]);
        self->w = (ap_uint<32>)(x[4]);
        self->k = (ap_uint<32>)(x[5]);
    }

    template<int word_bw>
    void read_array(const ap_uint<word_bw> x[]) {
        read_array_impl(word_bw_tag<word_bw>{}, this, x);
    }

    template<int word_bw>
    static void read_stream_impl(word_bw_tag<word_bw>, PoolCmd* self, hls::stream<ap_uint<word_bw>> &s) {
        static_assert(word_bw < 0, "Unsupported word_bw for read_stream");
        (void)self;
        (void)s;
    }

    static void read_stream_impl(word_bw_tag<32>, PoolCmd* self, hls::stream<ap_uint<32>> &s) {
            ap_uint<32> w = 0;
        w = s.read();
        self->magic = (ap_uint<32>)(w);
        w = s.read();
        self->tx_id = (ap_uint<32>)(w);
        w = s.read();
        self->opcode = (ap_uint<32>)(w);
        w = s.read();
        self->h = (ap_uint<32>)(w);
        w = s.read();
        self->w = (ap_uint<32>)(w);
        w = s.read();
        self->k = (ap_uint<32>)(w);
    }

    template<int word_bw>
    void read_stream(hls::stream<ap_uint<word_bw>> &s) {
        read_stream_impl(word_bw_tag<word_bw>{}, this, s);
    }

    template<int word_bw>
    static void read_axi4_stream_impl(word_bw_tag<word_bw>, PoolCmd* self, hls::stream<streamutils::axi4s_word<word_bw>> &s, streamutils::tlast_status &tl) {
        static_assert(word_bw < 0, "Unsupported word_bw for read_axi4_stream");
        (void)self;
        (void)s;
        (void)tl;
    }

    static void read_axi4_stream_impl(word_bw_tag<32>, PoolCmd* self, hls::stream<streamutils::axi4s_word<32>> &s, streamutils::tlast_status &tl) {
            ap_uint<32> w = 0;
            tl = streamutils::tlast_status::no_tlast;
            bool last = false;
        if (last) {
            tl = streamutils::tlast_status::tlast_early;
            return;
        }
        {
            auto axis_word = s.read();
            w = axis_word.data;
            last = axis_word.last;
        }
        self->magic = (ap_uint<32>)(w);
        if (tl != streamutils::tlast_status::no_tlast) {
            tl = streamutils::tlast_status::tlast_early;
            return;
        }
        if (last) {
            tl = streamutils::tlast_status::tlast_early;
            return;
        }
        {
            auto axis_word = s.read();
            w = axis_word.data;
            last = axis_word.last;
        }
        self->tx_id = (ap_uint<32>)(w);
        if (tl != streamutils::tlast_status::no_tlast) {
            tl = streamutils::tlast_status::tlast_early;
            return;
        }
        if (last) {
            tl = streamutils::tlast_status::tlast_early;
            return;
        }
        {
            auto axis_word = s.read();
            w = axis_word.data;
            last = axis_word.last;
        }
        self->opcode = (ap_uint<32>)(w);
        if (tl != streamutils::tlast_status::no_tlast) {
            tl = streamutils::tlast_status::tlast_early;
            return;
        }
        if (last) {
            tl = streamutils::tlast_status::tlast_early;
            return;
        }
        {
            auto axis_word = s.read();
            w = axis_word.data;
            last = axis_word.last;
        }
        self->h = (ap_uint<32>)(w);
        if (tl != streamutils::tlast_status::no_tlast) {
            tl = streamutils::tlast_status::tlast_early;
            return;
        }
        if (last) {
            tl = streamutils::tlast_status::tlast_early;
            return;
        }
        {
            auto axis_word = s.read();
            w = axis_word.data;
            last = axis_word.last;
        }
        self->w = (ap_uint<32>)(w);
        if (tl != streamutils::tlast_status::no_tlast) {
            tl = streamutils::tlast_status::tlast_early;
            return;
        }
        if (last) {
            tl = streamutils::tlast_status::tlast_early;
            return;
        }
        {
            auto axis_word = s.read();
            w = axis_word.data;
            last = axis_word.last;
        }
        self->k = (ap_uint<32>)(w);
        if (tl != streamutils::tlast_status::no_tlast) {
            return;
        }
        if (last) {
            tl = streamutils::tlast_status::tlast_at_end;
        }
    }

    template<int word_bw>
    void read_axi4_stream(hls::stream<streamutils::axi4s_word<word_bw>> &s, streamutils::tlast_status &tl) {
        read_axi4_stream_impl(word_bw_tag<word_bw>{}, this, s, tl);
    }

    template<int word_bw>
    void read_axi4_stream(hls::stream<streamutils::axi4s_word<word_bw>> &s) {
        streamutils::tlast_status tl = streamutils::tlast_status::no_tlast;
        read_axi4_stream<word_bw>(s, tl);
    }

#ifdef WAVEFLOW_ENABLE_POOL_CMD_TB_H_MEMBERS
    void dump_json(std::ostream& os, int indent = 2, int level = 0) const;
    void load_json(const std::string& json_text, size_t& pos);
    void load_json(std::istream& is);
    void dump_json_file(const char* file_path, int indent = 2) const;
    void load_json_file(const char* file_path);
#endif
};

#endif // INCLUDE_POOL_CMD_H