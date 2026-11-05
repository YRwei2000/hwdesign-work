"""Independent model gate, fixture export and exact recorded-output comparison."""
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
import numpy as np
from waveflow.utils.burst_io import StreamBurst, write_bursts, read_bursts
from pool import evaluate, stream_model, WouldBlock
from oracle import reference
from scenarios import scenarios

ROOT = Path(__file__).resolve().parent
def save(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,indent=2)+"\n")
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def freeze():
    return {n:sha(ROOT/n) for n in ("prompt.md","pool.py","oracle.py","scenarios.py")}
def bursts(words):
    result,pending=[],[]
    for v,last in words:
        pending.append(v)
        if last:
            result.append(StreamBurst(np.asarray(pending,np.uint64),True))
            pending=[]
    if pending:
        result.append(StreamBurst(np.asarray(pending,np.uint64),False))
    return result
def read_words(path):
    return [[int(v),int(b.tlast and i==len(b.words)-1)]
            for b in read_bursts(path) for i,v in enumerate(b.words)]
def compare(got,want):
    return [f"{key} differs" for key in ("words","status","consumed","unread") if got[key]!=want[key]]
def arithmetic_gate():
    rng=np.random.default_rng(55112026)
    records=[]
    def check(name,a,k,literal=None):
        a=np.asarray(a,np.float32)
        got=evaluate(a,k).view(np.uint32)
        expected=reference(a,k).view(np.uint32)
        okay=np.array_equal(got,expected) and (literal is None or got.ravel().tolist()==literal)
        records.append(dict(name=name,shape=list(a.shape),k=k,input_bits=a.view(np.uint32).tolist(),
                            expected_bits=expected.tolist(),model_bits=got.tolist(),literal_bits=literal,pass_=bool(okay)))
    check("worked",np.arange(1,17,dtype=np.float32).reshape(4,4),2,
          [0x40c00000,0x41000000,0x41600000,0x41800000])
    check("negative",-np.arange(1,17,dtype=np.float32).reshape(4,4),2,
          [0xbf800000,0xc0400000,0xc1100000,0xc1300000])
    check("zero_ties_both_orders",np.array([0x80000000,0,0,0x80000000,0,0x80000000,0x80000000,0],np.uint32)
          .view(np.float32).reshape(2,4),2,[0x80000000,0])
    check("finite_bounds_k1",np.array([0x00800000,0x80800000,0x7f7fffff,0xff7fffff],np.uint32)
          .view(np.float32).reshape(2,2),1,[0x00800000,0x80800000,0x7f7fffff,0xff7fffff])
    for i in range(512):
        k=int(rng.integers(1,9));h=k*int(rng.integers(1,64//k+1));w=k*int(rng.integers(1,64//k+1))
        # All supported binary32 normal exponents; ties/zeros deliberately frequent.
        raw=rng.integers(0,2**32,size=(h,w),dtype=np.uint32)
        raw=(raw & np.uint32(0x807fffff)) | (rng.integers(1,255,size=(h,w),dtype=np.uint32)<<23)
        if i%3==0:
            raw.ravel()[::3]=np.uint32(0x80000000 if i%2 else 0)
        if i%7==0:
            raw[:]=raw[0,0]
        check(f"random_{i:03}",raw.view(np.float32),k)
    save(ROOT/"evidence/arithmetic.json",records)
    assert all(r["pass_"] for r in records)
    return len(records)
def model_gate():
    count=arithmetic_gate()
    report={};cases=scenarios()
    for c in cases:
        d=ROOT/"data"/c.name;expected=c.expected();got=stream_model(c.words)
        # Independent count invariant prevents shared empty-array placeholders.
        assert len(expected["words"])==sum(3+a["result_count"] for a in c.actions if a["kind"]=="COMPUTE")
        save(d/"intent.json",dict(purpose=c.purpose,actions=c.actions))
        save(d/"input.json",c.words);save(d/"expected.json",expected);save(d/"model.json",got)
        write_bursts(bursts(c.words),d/"in")
        write_bursts(bursts(c.out),d/"expected")
        for stage in ("csim","cosim"):
            (d/stage).mkdir(exist_ok=True);(d/(stage+"_unread")).mkdir(exist_ok=True)
        problems=compare(got,expected)
        report[c.name]=dict(pass_=not problems,problems=problems)
        print(c.name,"PASS" if not problems else problems)
    (ROOT/"data/scenarios.txt").write_text("\n".join(c.name for c in cases)+"\n")
    save(ROOT/"evidence/check_model.json",report)
    wanted=cases[0].expected();rejections={}
    for key in ("result_bit","missing_tlast","wrong_status","extra_read","fake_result"):
        got=copy.deepcopy(wanted)
        if key=="result_bit":got["words"][3][0]^=1
        elif key=="missing_tlast":got["words"][-1][1]=0
        elif key=="wrong_status":got["status"]["error"]=1
        elif key=="extra_read":got["consumed"]+=1
        else:got["words"].append([0,1])
        p=compare(got,wanted);rejections[key]=dict(rejected=bool(p),problems=p)
    save(ROOT/"evidence/checker_rejections.json",rejections)
    assert all(r["rejected"] for r in rejections.values())
    assert all(r["pass_"] for r in report.values())
    for i,c in enumerate(cases):
        if c.status["halted"]:
            assert cases[i+1].name=="R_"+c.name and not cases[i+1].status["halted"]
    # Model's offline incomplete-input exception has no protocol error encoding.
    try: stream_model([])
    except WouldBlock: pass
    else: raise AssertionError("Empty input must wait, not report a hardware error")
    save(ROOT/"evidence/model_gate.json",dict(pass_=True,utc=datetime.now(timezone.utc).isoformat(),
         prompt_version="v2",arithmetic_vectors=count,activations=len(cases),
         errors=sum(c.status["halted"] for c in cases),recoveries=sum(c.name.startswith("R_") for c in cases),
         frozen_sources=freeze()))
    print("INDEPENDENT MODEL GATE PASS",count,"arithmetic cases;",len(cases),"activations")
def check_stage(stage):
    gate=json.loads((ROOT/"evidence/model_gate.json").read_text())
    assert freeze()==gate["frozen_sources"],"Frozen model/intent sources changed"
    reports={}
    for c in scenarios():
        d=ROOT/"data"/c.name
        try:
            st=json.loads((d/stage/"status.json").read_text())
            got=dict(words=read_words(d/stage),status={k:st[k] for k in ("halted","error","tx_id")},
                     consumed=st["consumed"],unread=read_words(d/(stage+"_unread")))
            p=compare(got,c.expected())+compare(got,json.loads((d/"model.json").read_text()))
            save(d/stage/"observed.json",got)
        except (OSError,KeyError) as exc:p=[str(exc)]
        reports[c.name]=dict(pass_=not p,problems=p)
        print(stage,c.name,"PASS" if not p else p)
    save(ROOT/"evidence"/f"check_{stage}.json",reports)
    assert all(r["pass_"] for r in reports.values()),stage+" comparison failed"
    print(stage,"EXACT COMPARISON PASS",len(reports),"activations")
if __name__=="__main__":
    model_gate() if sys.argv[1]=="model" else check_stage(sys.argv[1])
