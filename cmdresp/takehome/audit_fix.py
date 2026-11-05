"""Validate retained evidence/source hashes and report links; NO simulation."""
import hashlib
import json
from pathlib import Path
import re
from verify import ROOT,sha,save,freeze

def audit():
    fix=ROOT/"evidence/fix_v2"
    ready=json.loads((fix/"final_ready.json").read_text())
    source=json.loads((fix/"source_manifest.json").read_text())
    assert all(sha(ROOT/n)==v for n,v in source.items()),"Current source differs from verified source manifest"
    old=json.loads((fix/"reuse_validation.json").read_text())
    assert freeze()==old["model_freeze"]
    assert all(sha(ROOT/n)==v for n,v in old["original_evidence_sha256"].items()),"Original evidence changed"
    for filename,count in (("check_csim_fix.json",66),("check_cosim_fix.json",66),("check_raw_rtl_vectors.json",66),
                           ("check_rtl_wave.json",66),("check_protocol.json",69)):
        report=json.loads((fix/filename).read_text())
        assert len(report)==count and all(r["pass_"] for r in report.values()),filename
    for filename in ("results.md","results_initial.md","layout.md","README.md"):
        for target in re.findall(r"\]\(([^)]+)\)",(ROOT/filename).read_text()):
            if "://" not in target:
                destination=ROOT/target.split('#')[0]
                # This audit creates its own linked result only after all checks.
                if destination!=fix/"integrity.json":
                    assert destination.exists(),(filename,target)
    artifact_path=fix/"artifact_manifest.json"
    if artifact_path.exists():
        artifacts=json.loads(artifact_path.read_text())
        assert all(sha(ROOT/n)==v for n,v in artifacts.items()),"Retained raw artifact changed"
    else:
        artifacts={str(p.relative_to(ROOT)):sha(p) for p in fix.rglob("*") if p.is_file()
                   and p.name not in ("artifact_manifest.json","integrity.json","source_manifest.json","final_ready.json")
                   and "baseline" not in p.parts}
        save(artifact_path,artifacts)
    result=dict(pass_=ready["pass_"],relative_links_exist=True,current_source_hashes_checked=len(source),
                retained_artifacts_checked=len(artifacts),original_evidence_unchanged=True,model_freeze_unchanged=True,
                standard_activations=66,full_fixture_protocol_activations=69,
                synthesis_clock_ns=json.loads((fix/"synthesis.json").read_text())["estimated_ns"],
                input_cycles=json.loads((fix/"performance.json").read_text())["input_cycles"])
    save(fix/"integrity.json",result)
    assert (fix/"integrity.json").exists()
    print("RETAINED-EVIDENCE AUDIT PASS",len(source),"source files;",len(artifacts),"artifacts; no hardware execution")
if __name__=="__main__":audit()
