"""Generate only Waveflow interfaces/serializers, using the actual Vitis version."""
from pathlib import Path
from waveflow.build.build import BuildConfig, BuildDag
from waveflow.build.hwcodegen_steps import HlsCodegenStep
from waveflow.build.streamutils import StreamUtilsStep
from waveflow.hw.dataschema import DataSchemaStep
from waveflow.hw.arrayutils import ArrayUtilsStep
from scale_offset import CmdHdr, RespHdr, Float32, ScaleOffset

ROOT = Path(__file__).resolve().parent


def generate():
    cfg = BuildConfig(root_dir=ROOT, vitis_version="2026.1")
    dag = BuildDag()
    dag.add(StreamUtilsStep(output_dir="include"))
    for cls in (CmdHdr, RespHdr):
        dag.add(DataSchemaStep(cls, word_bw_supported=[32], include_dir="include"))
    dag.add(ArrayUtilsStep(Float32, [32]))
    results = dag.run(cfg)
    assert all(r.success for r in results.values()), results
    HlsCodegenStep(name="gen_kernel", comp_class=ScaleOffset, source_artifact="body_source",
                   output_dir="gen", impl_dir=".").run(cfg)


if __name__ == "__main__":
    generate()
