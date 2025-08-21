# tests/test_docker_run_qwen.py
import os
import shutil
import subprocess
from pathlib import Path
import pytest

def _have_nvidia_smi() -> bool:
    return shutil.which("nvidia-smi") is not None

def test_gpu_visible_or_skip():
    """
    Verify that the container can see a GPU. If not, skip (useful on CPU-only CI).
    """
    if not _have_nvidia_smi():
        pytest.skip("nvidia-smi not found in container; skipping GPU visibility test")
    try:
        out = subprocess.check_output(["nvidia-smi", "-L"], text=True)
        assert "GPU" in out
        print(out)
    except Exception as e:
        pytest.fail(f"nvidia-smi failed: {e}")

def test_llama_cpp_built_with_cuda():
    """
    Verify the llama-cpp-python backend was compiled with CUDA support
    by inspecting llama_print_system_info().
    """
    import llama_cpp.llama_cpp as llcp  # low-level wrapper
    try:
        info = llcp.llama_print_system_info().decode() if isinstance(llcp.llama_print_system_info(), bytes) else llcp.llama_print_system_info()
    except Exception:
        # Some builds may expose it under a different binding; fallback:
        info = str(llcp.llama_print_system_info())
    print(info)
    assert "CUDA" in info or "cuBLAS" in info or "GGML_CUDA" in info, \
        "Expected CUDA/cuBLAS/GGML_CUDA flags in llama system info; build may be CPU-only."

@pytest.mark.timeout(60)
def test_qwen_runs_locally_with_cuda_offload_if_model_present():
    """
    If a small Qwen GGUF exists at MODEL_PATH, load it and run a tiny prompt
    with n_gpu_layers=-1 (full offload). If model is absent, skip.
    """
    from llama_cpp import Llama

    model_dir = Path(os.environ.get("MODEL_PATH", "/app/models"))
    # You can adjust this filename to whatever you actually mount
    candidate_names = [
        "Qwen2.5-7B-Instruct-Q6_K_L.gguf"
    ]
    model_path = None
    for name in candidate_names:
        p = model_dir / name
        if p.exists():
            model_path = str(p)
            break

    if not model_path:
        pytest.skip("No Qwen GGUF model found under MODEL_PATH; skipping runtime test")

    llm = Llama(
        model_path=model_path,
        n_ctx=1024,
        n_gpu_layers=-1,   # request full GPU offload
        n_threads=4,
        vocab_only=False,
        verbose=False,
    )

    prompt = "Q: Say 'hello from qwen' in one short sentence.\nA:"
    out = llm(prompt, max_tokens=16, temperature=0.2, echo=False)
    text = (out.get("choices") or [{}])[0].get("text", "").strip()
    print(text)
    assert isinstance(text, str) and len(text) > 0
