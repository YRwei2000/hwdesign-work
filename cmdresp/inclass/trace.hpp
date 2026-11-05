#pragma once
// C simulation observations only. No stream accesses or status changes here.
#ifndef __SYNTHESIS__
#include <fstream>
#include <string>
#include <vector>
namespace scale_offset_trace {
struct Event { std::string kind; unsigned tx, index, remaining, out_count; };
inline std::vector<Event>& events() { static std::vector<Event> value; return value; }
inline void add(const char* kind, unsigned tx, unsigned index, unsigned remaining, unsigned out_count) {
    events().push_back({kind, tx, index, remaining, out_count});
}
inline void save(const std::string& path) {
    std::ofstream f(path);
    for (const auto& e : events())
        f << "{\"kind\":\"" << e.kind << "\",\"tx\":" << e.tx
          << ",\"index\":" << e.index << ",\"remaining\":" << e.remaining
          << ",\"out_count\":" << e.out_count << "}\n";
}
}
#define SO_EVENT(kind, tx, index) scale_offset_trace::add(kind, (unsigned)(tx), (unsigned)(index), s_in.size(), m_out.size())
#else
#define SO_EVENT(kind, tx, index) ((void)0)
#endif
