#pragma once
// Untimed C execution observations, excluded from synthesized hardware.
#ifndef __SYNTHESIS__
#include <fstream>
#include <string>
#include <vector>
namespace pool_trace {
struct Event { std::string kind; unsigned tx,index,remaining,output; };
inline std::vector<Event>& events() { static std::vector<Event> e; return e; }
inline void add(const char* kind,unsigned tx,unsigned index,unsigned rem,unsigned out) {
    events().push_back({kind,tx,index,rem,out});
}
inline void save(const std::string& path) {
    std::ofstream f(path);
    for(const auto& e:events()) f << "{\"kind\":\"" << e.kind << "\",\"tx\":" << e.tx
      << ",\"index\":" << e.index << ",\"remaining\":" << e.remaining
      << ",\"output\":" << e.output << "}\n";
}
}
#define POOL_EVENT(kind,tx,index) pool_trace::add(kind,(unsigned)(tx),(unsigned)(index),s_in.size(),m_out.size())
#else
#define POOL_EVENT(kind,tx,index) ((void)0)
#endif
