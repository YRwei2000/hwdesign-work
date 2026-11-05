"""Project-local Waveflow emitter configuration: explicit AXIS register policy.

The installed kernel_signature emitter has no per-port register-mode option.
Configure its returned signature DURING generation, not generated files after
generation. All prototypes, status interfaces, schemas and serializers remain
Waveflow's. The original installed emitter is restored immediately afterward.
"""
from pathlib import Path
import difflib
from waveflow.build import hwgen
from waveflow.build.build import BuildConfig
from waveflow.build.hwcodegen_steps import HlsCodegenStep
from pool import PoolAccel
from verify import ROOT,save,sha

def generate():
    original=hwgen.kernel_signature
    def configured(comp,variant_suffix=""):
        signature=original(comp,variant_suffix=variant_suffix)
        for name in ("s_in","m_out"):
            old=f"#pragma HLS INTERFACE axis port={name}\n"
            new=f"#pragma HLS INTERFACE axis port={name} register_mode=off\n"
            assert signature.count(old)==1,(name,signature)
            signature=signature.replace(old,new)
        return signature
    hwgen.kernel_signature=configured
    try:
        cfg=BuildConfig(root_dir=ROOT,vitis_version="2026.1")
        HlsCodegenStep(name="gen_off_kernel",comp_class=PoolAccel,source_artifact="off_body_source",
                       output_dir="gen_off",impl_dir=".").run(cfg)
    finally:
        hwgen.kernel_signature=original
    before=(ROOT/"gen/max_pool.cpp").read_text();after=(ROOT/"gen_off/max_pool.cpp").read_text()
    normalized=after.replace(" register_mode=off","")
    assert before==normalized,"Only the two interface policy options may change"
    assert (ROOT/"gen/max_pool.hpp").read_bytes()==(ROOT/"gen_off/max_pool.hpp").read_bytes()
    save(ROOT/"evidence/fix_v2/generation.json",dict(generator="Waveflow HlsCodegenStep",
         policy={"s_in":"off","m_out":"off"},installed_emitter_sha256=sha(Path(hwgen.__file__)),
         installed_package_modified=False,generated_files_postedited=False,only_two_pragma_options_changed=True,
         generated_cpp_sha256=sha(ROOT/"gen_off/max_pool.cpp"),
         diff=list(difflib.unified_diff(before.splitlines(),after.splitlines(),fromfile="gen/max_pool.cpp",tofile="gen_off/max_pool.cpp"))))
    print("Generated boundary: only two AXIS register_mode=off options changed")
if __name__=="__main__":generate()
