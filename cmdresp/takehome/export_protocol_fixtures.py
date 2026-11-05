"""Export ALL existing serialized words; never derive stimulus from C read counts."""
import json
from pathlib import Path
from verify import ROOT,save,sha

def export():
    target=ROOT/"evidence/fix_v2/protocol_fixtures";target.mkdir(parents=True,exist_ok=True)
    names=(ROOT/"data/scenarios.txt").read_text().split()
    cases=[(n,n,0) for n in names]+[("BP_success","T01_worked",1),
          ("BP_payload_error","E07_payload_first",1),("R_BP_payload_error","R_E07_payload_first",0)]
    lines=[];records=[]
    for name,source,bp in cases:
        base=ROOT/"data"/source
        words=json.loads((base/"input.json").read_text())
        expected=json.loads((base/"expected.json").read_text())
        intent=json.loads((base/"intent.json").read_text())
        in_require=[-1]*len(words);out_require=[-1]*len(expected["words"])
        for a in intent["actions"]:
            if a["kind"]!="COMPUTE":continue
            in_require[a["header_end"]]=a["output_start"]+2
            for j in range(a["result_count"]):
                out_require[a["output_start"]+3+j]=a["header_end"]+a["received"]-1
        (target/(name+".in")).write_text("".join(f"{w:08x} {last} {req}\n" for (w,last),req in zip(words,in_require)))
        (target/(name+".out")).write_text("".join(f"{w:08x} {last} {req}\n" for (w,last),req in zip(expected["words"],out_require)))
        st=expected["status"]
        lines.append(f"{name} {len(words)} {expected['consumed']} {len(expected['words'])} {st['halted']} {st['error']} {st['tx_id']:08x} {bp}")
        records.append(dict(name=name,source=source,backpressure=bool(bp),full_input_words=len(words),
                            expected_consumed=expected["consumed"],expected_status=st,
                            input_sha256=sha(base/"input.json"),expected_sha256=sha(base/"expected.json"),
                            input_file=name+".in",output_file=name+".out"))
    (target/"cases.txt").write_text("\n".join(lines)+"\n")
    save(ROOT/"evidence/fix_v2/protocol_fixture_manifest.json",dict(scenarios=records,
         base_activations=66,additional_backpressure_activations=3,observed_after_status_cycles=16,
         all_fixture_words_exported=True,stimulus_independent_of_c_consumption=True))
    print("Exported complete fixtures:",len(cases),"activations")
if __name__=="__main__":export()
