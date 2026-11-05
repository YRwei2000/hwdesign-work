"""Measure recorded RTL waveforms; this is not a Python timing model."""
from bisect import bisect_left
import gzip
import json
from pathlib import Path
import shutil
import statistics
import tempfile
import xml.etree.ElementTree as ET
from vcdvcd import VCDVCD
from verify import ROOT, save

def retain_synthesis(project="pool_proj",evidence_dir=None):
    evidence_dir=Path(evidence_dir) if evidence_dir else ROOT/"evidence"
    src=ROOT/project/"solution1/syn"
    dst=evidence_dir/"synthesis";dst.mkdir(parents=True,exist_ok=True)
    for pattern in ("*.rpt","*.xml"):
        for p in (src/"report").glob(pattern):shutil.copy2(p,dst/p.name)
    shutil.copy2(src/"verilog/max_pool_control_s_axi.v",dst/"max_pool_control_s_axi.v")
    top=ET.parse(dst/"max_pool_csynth.xml").getroot()
    loops={}
    for p in dst.glob("*_csynth.xml"):
        doc=ET.parse(p).getroot()
        loops[p.name]=[{child.tag:child.text for child in node if len(child)==0}
                      for node in doc.findall(".//SummaryOfLoopLatency/*")]
    result=dict(part=top.findtext(".//Part"),target_ns=float(top.findtext(".//TargetClockPeriod")),
                estimated_ns=float(top.findtext(".//EstimatedClockPeriod")),
                uncertainty_ns=float(top.findtext(".//ClockUncertainty")),
                resources={x.tag:int(x.text) for x in top.findall(".//AreaEstimates/Resources/*")},
                loops=loops,source=str((dst/"max_pool_csynth.xml").relative_to(ROOT)))
    result["clock_pass"]=result["estimated_ns"]<10
    save(evidence_dir/"synthesis.json",result)
    return result

def analyze_wave(path,evidence_dir=None):
    evidence_dir=Path(evidence_dir) if evidence_dir else ROOT/"evidence"
    meta=VCDVCD(str(path),only_sigs=True)
    mapping={}
    for key in ("ap_clk","s_in_TDATA","s_in_TVALID","s_in_TREADY","s_in_TLAST",
                "m_out_TDATA","m_out_TVALID","m_out_TREADY","m_out_TLAST"):
        choices=[s for s in meta.signals if "AESL_inst_max_pool" in s
                 and s.split(".")[-1].split("[")[0]==key]
        assert len(choices)==1,(key,choices)
        mapping[key]=choices[0]
    reader=VCDVCD(str(path),signals=list(mapping.values()))
    tv={k:reader[v].tv for k,v in mapping.items()}
    times={k:[x[0] for x in v] for k,v in tv.items()}
    def at(key,time):
        i=bisect_left(times[key],time)-1 # pre-edge stable value, never the post-edge update
        value=tv[key][i][1] if i>=0 else "x"
        return None if any(c in value.lower() for c in "xz") else int(value,2)
    edges=[t for t,v in tv["ap_clk"] if v=="1"]
    period=statistics.median(b-a for a,b in zip(edges,edges[1:]))
    tick_ns=float(reader.timescale["timescale"])*1e9
    input_events=[];output_events=[];input_valid=[];output_ready=[]
    for cycle,t in enumerate(edges):
        iv,ir=at("s_in_TVALID",t),at("s_in_TREADY",t)
        ov,orr=at("m_out_TVALID",t),at("m_out_TREADY",t)
        input_valid.append(iv);output_ready.append(orr)
        if iv==ir==1:
            input_events.append(dict(cycle=cycle,word=at("s_in_TDATA",t),last=at("s_in_TLAST",t)))
        if ov==orr==1:
            output_events.append(dict(cycle=cycle,word=at("m_out_TDATA",t),last=at("m_out_TLAST",t)))
    save(evidence_dir/"wave_signals.json",dict(mapping=mapping,clock_period_ticks=period,
         tick_ns=tick_ns,clock_ns=period*tick_ns,sampling="strictly before rising edge"))
    with gzip.open(evidence_dir/"rtl_handshakes.jsonl.gz","wt") as f:
        for side,events in (("input",input_events),("output",output_events)):
            for e in events:f.write(json.dumps(dict(side=side,**e))+"\n")
    names=(ROOT/"data/scenarios.txt").read_text().split();report={};pi=po=0;performance=None
    for name in names:
        d=ROOT/"data"/name;expected=json.loads((d/"expected.json").read_text())
        stimulus=json.loads((d/"input.json").read_text());intent=json.loads((d/"intent.json").read_text())
        ni,no=expected["consumed"],len(expected["words"])
        ins,outs=input_events[pi:pi+ni],output_events[po:po+no]
        problems=[]
        if [[e["word"],e["last"]] for e in ins]!=stimulus[:ni]:problems.append("RTL input prefix differs")
        if [[e["word"],e["last"]] for e in outs]!=expected["words"]:problems.append("RTL output words/TLAST differ")
        ordering=[]
        for a in intent["actions"]:
            if a["kind"]!="COMPUTE":continue
            first=ins[a["header_end"]]["cycle"]
            last=ins[a["header_end"]+a["received"]-1]["cycle"]
            resp=outs[a["output_start"]+2]["cycle"]
            hdr_before_payload=resp<first
            result_after_input=(a["error"]!=0 or outs[a["output_start"]+3]["cycle"]>last)
            ordering.append(dict(tx_id=a["tx_id"],response_last_cycle=resp,first_input_cycle=first,
                                 last_input_cycle=last,header_before_payload=hdr_before_payload,
                                 results_after_valid_input=result_after_input))
            if not hdr_before_payload:problems.append(f"tx {a['tx_id']}: external payload accepted before response completed")
            if not result_after_input:problems.append(f"tx {a['tx_id']}: result transferred before input validated")
            if name=="T07_performance":
                end=outs[-1]["cycle"]
                cycles=last-first+1;total=end-first+1
                performance=dict(scenario=name,input_samples=4096,output_samples=1024,
                     first_input_cycle=first,last_input_cycle=last,last_result_cycle=end,
                     input_cycles=cycles,total_latency_cycles=total,clock_ns=period*tick_ns,
                     total_latency_ns=total*period*tick_ns,input_samples_per_cycle=4096/cycles,
                     end_to_end_results_per_cycle=1024/total,
                     input_megasamples_per_second=(4096/cycles)/(period*tick_ns)*1000,
                     no_host_input_pauses=all(x==1 for x in input_valid[first:last+1]),
                     no_output_backpressure=all(x==1 for x in output_ready[first:end+1]),
                     input_cycle_target=8192,input_cycle_target_pass=cycles<=8192)
        report[name]=dict(pass_=not problems,problems=problems,ordering=ordering,
                          input_count=ni,output_count=no)
        pi+=ni;po+=no
    assert pi==len(input_events),(pi,len(input_events))
    assert po==len(output_events),(po,len(output_events))
    save(evidence_dir/"check_rtl_wave.json",report)
    save(evidence_dir/"performance.json",performance)
    print(json.dumps(performance,indent=2))
    print("RTL WAVE CHECK",sum(r["pass_"] for r in report.values()),"/",len(report))
    return report

if __name__=="__main__":
    if (ROOT/"pool_proj/solution1/syn/report").exists():retain_synthesis()
    path=ROOT/"evidence/ports.vcd"
    if path.exists():analyze_wave(path)
    else:
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/"ports.vcd"
            with gzip.open(ROOT/"evidence/ports.vcd.gz","rb") as src,target.open("wb") as dst:
                shutil.copyfileobj(src,dst)
            analyze_wave(target)
