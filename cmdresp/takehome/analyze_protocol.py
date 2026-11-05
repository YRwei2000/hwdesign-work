"""Independent post-check of actual pin waveforms, not a timing prediction."""
from bisect import bisect_left
from collections import defaultdict,deque
import gzip
import json
from pathlib import Path
from vcdvcd import VCDVCD
from verify import ROOT,save

class Pins:
    def __init__(self,path):
        self.v=(VCDVCD(vcd_string=gzip.open(path,"rt").read()) if str(path).endswith(".gz") else VCDVCD(str(path)))
        self.names={}
        keys=["ap_clk","ap_rst_n","s_in_TDATA","s_in_TVALID","s_in_TREADY","s_in_TLAST",
              "m_out_TDATA","m_out_TVALID","m_out_TREADY","m_out_TLAST",
              "s_axi_control_ARADDR","s_axi_control_ARVALID","s_axi_control_ARREADY",
              "s_axi_control_RDATA","s_axi_control_RVALID","s_axi_control_RREADY"]
        for key in keys:
            hits=[n for n in self.v.signals if ".dut." in n and n.split(".")[-1].split("[")[0]==key]
            assert len(hits)==1,(key,hits)
            self.names[key]=hits[0]
        for key in ("case_index","active"):
            self.names[key]=next(n for n in self.v.signals if n.split(".")[-1].split("[")[0]==key)
        self.tv={k:self.v[n].tv for k,n in self.names.items()}
        self.times={k:[t for t,v in values] for k,values in self.tv.items()}
        self.edges=[t for t,v in self.tv["ap_clk"] if v=="1"]
    def at(self,key,t):
        i=bisect_left(self.times[key],t)-1
        s=self.tv[key][i][1] if i>=0 else "x"
        return None if any(c in s.lower() for c in "xz") else int(s,2)

def analyze():
    target=ROOT/"evidence/fix_v2";folder=target/"protocol"
    manifest=json.loads((target/"protocol_fixture_manifest.json").read_text())["scenarios"]
    summaries={}
    for line in (folder/"summary.txt").read_text().splitlines():
        v=line.split();summaries[v[1]]=dict(index=int(v[0]),full=int(v[2]),stop=int(v[3]),
            received=int(v[4]),expected_outputs=int(v[5]),outputs=int(v[6]),error=int(v[7]),
            tx_id=int(v[8],16),failures=int(v[9]),backpressure_cycles=int(v[10]),done=int(v[11]),end=int(v[12]))
    assert len(summaries)==69
    path=folder/"protocol.vcd"
    if not path.exists():path=folder/"protocol.vcd.gz"
    pins=Pins(path)
    inputs=defaultdict(list);outputs=defaultdict(list);states=defaultdict(list);reads=defaultdict(list)
    addresses=deque();reset_edges=defaultdict(int)
    for cycle,t in enumerate(pins.edges,1):
        index=pins.at("case_index",t)
        if pins.at("ap_rst_n",t)==0:reset_edges[index]+=1
        if pins.at("ap_rst_n",t)!=1 or pins.at("active",t)!=1:
            addresses.clear();continue
        val={k:pins.at(k,t) for k in pins.names if k not in ("case_index","active","ap_clk","ap_rst_n")}
        states[index].append(dict(cycle=cycle,**val))
        if val["s_in_TVALID"]==val["s_in_TREADY"]==1:
            inputs[index].append(dict(cycle=cycle,word=val["s_in_TDATA"],last=val["s_in_TLAST"]))
        if val["m_out_TVALID"]==val["m_out_TREADY"]==1:
            outputs[index].append(dict(cycle=cycle,word=val["m_out_TDATA"],last=val["m_out_TLAST"]))
        if val["s_axi_control_ARVALID"]==val["s_axi_control_ARREADY"]==1:
            addresses.append(val["s_axi_control_ARADDR"])
        if val["s_axi_control_RVALID"]==val["s_axi_control_RREADY"]==1:
            assert addresses
            reads[index].append(dict(cycle=cycle,address=addresses.popleft(),data=val["s_axi_control_RDATA"]))
    report={}
    for i,record in enumerate(manifest):
        name=record["name"];source=ROOT/"data"/record["source"]
        expected=json.loads((source/"expected.json").read_text());words=json.loads((source/"input.json").read_text())
        actions=json.loads((source/"intent.json").read_text())["actions"]
        inp,out,st=inputs[i],outputs[i],states[i];summary=summaries[name];problems=[]
        if [[e["word"],e["last"]] for e in inp]!=words[:expected["consumed"]]:problems.append("external input prefix/count mismatch")
        if [[e["word"],e["last"]] for e in out]!=expected["words"]:problems.append("external output word/count/TLAST mismatch")
        actual_status={r["address"]:r["data"] for r in reads[i] if r["address"] in (16,32,48)}
        if actual_status!={16:expected["status"]["halted"],32:expected["status"]["error"],48:expected["status"]["tx_id"]}:problems.append("AXI-Lite status readback mismatch")
        if summary["failures"]!=0:problems.append("RTL self-check failures")
        ordering=[]
        for a in actions:
            if a["kind"]!="COMPUTE":continue
            first=inp[a["header_end"]]["cycle"];last=inp[a["header_end"]+a["received"]-1]["cycle"]
            resp=out[a["output_start"]+2]["cycle"]
            result_ok=a["error"]!=0 or out[a["output_start"]+3]["cycle"]>last
            okay=resp<first and result_ok
            ordering.append(dict(tx_id=a["tx_id"],response_last_cycle=resp,first_payload_cycle=first,
                 last_payload_cycle=last,pass_=okay,signals={"input":"rtl_protocol_tb.dut.s_in_TVALID/TREADY/TDATA/TLAST",
                 "output":"rtl_protocol_tb.dut.m_out_TVALID/TREADY/TDATA/TLAST"}))
            if not okay:problems.append("response/payload/result ordering mismatch")
        pending=None
        if expected["consumed"]<len(words):
            next_word,next_last=words[expected["consumed"]]
            held=[s for s in st if inp[-1]["cycle"]<s["cycle"]<=summary["end"]]
            good=bool(held) and all(s["s_in_TVALID"]==1 and s["s_in_TREADY"]==0 and
                  s["s_in_TDATA"]==next_word and s["s_in_TLAST"]==next_last for s in held)
            after_status=max(r["cycle"] for r in reads[i] if r["address"] in (16,32,48))
            observed=[s for s in held if s["cycle"]>after_status]
            good=good and len(observed)>=16
            pending=dict(pass_=good,word=next_word,last=next_last,held_cycles=len(held),
                         cycles_after_status=len(observed),unaccepted_words=len(words)-len(inp),
                         valid=1,ready=0,final_cycle=summary["end"])
            if not good:problems.append("pending word not held unaccepted through observation/reset")
        bp=None
        if record["backpressure"]:
            end=ordering[0]["response_last_cycle"]
            begin=out[1]["cycle"]
            stalled=[s for s in st if begin<s["cycle"]<end and s["m_out_TREADY"]==0]
            good=len(stalled)>=12 and not any(begin<e["cycle"]<=end for e in inp[6:])
            bp=dict(pass_=good,stalled_last_header_cycles=len(stalled),response_last_cycle=end,
                    first_payload_cycle=ordering[0]["first_payload_cycle"],
                    payload_handshakes_before_response_complete=sum(e["cycle"]<=end for e in inp[6:]),
                    first_stall_cycle=stalled[0]["cycle"] if stalled else None,last_stall_cycle=stalled[-1]["cycle"] if stalled else None)
            if not good:problems.append("response-last-word backpressure check failed")
        reset_before=reset_edges[i]>=5
        last_time=pins.edges[st[-1]["cycle"]-1]
        next_time=(pins.edges[states[i+1][0]["cycle"]-1] if i+1<len(manifest) else pins.v.endtime)
        reset_after=any(last_time<t<=next_time and v=="0" for t,v in pins.tv["ap_rst_n"])
        # Every error/pending beat must be reset, and each subsequent activation
        # must start with reset. There is no required recovery after the FINAL
        # normally completed, fully consumed activation (the simulator ends).
        reset_required=pending is not None or i+1<len(manifest)
        if not reset_before or (reset_required and not reset_after):problems.append("stream-path reset not observed")
        report[name]=dict(pass_=not problems,problems=problems,source=record["source"],full_fixture_words=len(words),
             received_words=len(inp),expected_received_words=expected["consumed"],output_words=len(out),
             actual_status=actual_status,ordering=ordering,pending=pending,backpressure=bp,
             reset_before_activation=reset_before,reset_cycles_before_activation=reset_edges[i],
             reset_after_observation=reset_after if reset_required else None,reset_after_required=reset_required)
    save(target/"check_protocol.json",report)
    save(target/"protocol_signals.json",dict(signals=pins.names,sampling="strictly before clock edge",cycle_numbering="1-based, first edge 5 ns"))
    with gzip.open(folder/"handshakes.jsonl.gz","wt") as f:
        for side,records in (("input",inputs),("output",outputs)):
            for index,events in records.items():
                for e in events:f.write(json.dumps(dict(case_index=index,side=side,**e))+"\n")
    assert all(r["pass_"] for r in report.values()),{n:r["problems"] for n,r in report.items() if not r["pass_"]}
    print("INDEPENDENT EXTERNAL RTL CHECK PASS",len(report),"activations")
    for name in ("E01_magic","E07_payload_first","BP_success","BP_payload_error"):
        print(name,json.dumps(report[name]))
if __name__=="__main__":analyze()
