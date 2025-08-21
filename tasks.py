"""
Invoke tasks for building, testing, and running the PF2e Society Scribe.
"""

import os
import sys
from pathlib import Path
from invoke import task, Context
from typing import Optional

# Configuration
PROJECT_NAME = "pf2e-society-scribe"
DOCKER_IMAGE = f"{PROJECT_NAME}:latest"
CONTAINER_NAME = f"{PROJECT_NAME}-container"
DEFAULT_PORT = 8000
CAMPAIGN_DATA_PATH = Path.home() / "pf2e-campaigns"
PROJECT_ROOT = Path(__file__).parent.resolve()

# Use a single, configurable Docker command everywhere.
# If you need sudo, set: export DOCKER_CMD="sudo docker"
DOCKER = os.environ.get("DOCKER_CMD", "docker")

def print_header(message: str) -> None:
    """Print a formatted header message."""
    print("\n" + "=" * 60)
    print(f"  {message}")
    print("=" * 60 + "\n")


@task
def build(
    c: Context,
    no_cache: bool = False,
    cuda_version: str = os.environ.get("CUDA_VERSION", "12.5.0"),
    arch_list: str = os.environ.get("GGML_CUDA_ARCH_LIST", "61"),
    progress: str = "plain",  # 'auto' or 'plain'
) -> None:
    """
    Build the Docker image (GPU-only) tuned for GTX 1080 Ti (Pascal, SM 6.1).

    Args:
        c: Invoke context
        no_cache: Build without using cache
        cuda_version: CUDA base image tag to use (default '12.5.0' for pre-built wheels)
        arch_list: GGML_CUDA_ARCH_LIST to compile (default '61' for Pascal)
        progress: docker build progress mode ('plain' or 'auto')
    """
    print_header("Building Docker Image (CUDA-only, Pascal SM 6.1)")

    cache_flag = "--no-cache" if no_cache else ""

    # Build args passed into the Dockerfile to ensure CUDA-only + Pascal arch
    build_args = (
        f"--build-arg CUDA_VERSION={cuda_version} "
        f"--build-arg GGML_CUDA_ARCH_LIST={arch_list} "
    )

    # If your env already defines DOCKER as "sudo docker", don't add another sudo.
    # Keep the explicit sudo here since your snippet showed 'sudo {DOCKER}'.
    cmd = (
        f"sudo {DOCKER} build {cache_flag} "
        f"--progress={progress} "
        f"{build_args}"
        f"-t {DOCKER_IMAGE} ."
    )

    print(f"Building image: {DOCKER_IMAGE}")
    print(f"Command: {cmd}")

    result = c.run(cmd, pty=True, warn=True)

    if result.exited == 0:
        print(f"\n✅ Successfully built {DOCKER_IMAGE}")
        c.run(f"{DOCKER} images {DOCKER_IMAGE}", pty=True)
    else:
        print(f"\n❌ Build failed with exit code {result.exited}")
        sys.exit(1)


@task
def test(
    c: Context,
    verbose: bool = False,
    coverage: bool = True,
    model_file: str = "Qwen2.5-7B-Instruct-Q6_K_L.gguf",
) -> None:
    """
    Run pytest in the CUDA container. Requires a model file under /app/models.
    The host-side file must exist at .tmp/models/<model_file>.
    """
    print_header("Running Tests in Docker (GPU-only)")

    # Ensure image exists
    if not c.run(f'{DOCKER} images -q {DOCKER_IMAGE}', hide=True).stdout.strip():
        print("Image not found. Building first...")
        build(c)

    # temp host dirs for mounts
    tmp_root = PROJECT_ROOT / ".tmp"
    models_host = tmp_root / "models"
    (tmp_root / "campaign-data").mkdir(parents=True, exist_ok=True)
    (tmp_root / "data").mkdir(parents=True, exist_ok=True)
    models_host.mkdir(parents=True, exist_ok=True)

    # Require the model to be present for a strict GPU-only test run
    model_host_path = models_host / model_file
    if not model_host_path.exists():
        print(f"❌ Test model not found: {model_host_path}")
        print("   Place your GGUF there or pass --model-file=<name> (file must be under .tmp/models).")
        sys.exit(1)

    # pytest cmd
    pytest_cmd = "pytest"
    if verbose:
        pytest_cmd += " -v"
    if coverage:
        pytest_cmd += " --cov=src --cov-report=term-missing --cov-report=html"

    # strict GPU-only
    gpu_bits = "--gpus all -e NVIDIA_VISIBLE_DEVICES=all -e NVIDIA_DRIVER_CAPABILITIES=compute,utility"

    env_vars = (
        "-e PYTHONPATH=/app "
        "-e CAMPAIGN_DATA_PATH=/app/campaign-data "
        "-e MODEL_PATH=/app/models "
        "-e PF2E_DB_PATH=/app/data/pf2e.db "
        "-e PORT=8000 "
        f"-e MODEL_FILE=/app/models/{model_file} "
    )

    cmd = (
        f"{DOCKER} run --rm {gpu_bits} "
        f"-v {PROJECT_ROOT}/tests:/app/tests:ro "
        f"-v {PROJECT_ROOT}/src:/app/src:ro "
        f"-v {tmp_root}/campaign-data:/app/campaign-data "
        f"-v {tmp_root}/data:/app/data "
        f"-v {models_host}:/app/models "
        f"{env_vars}"
        f"{DOCKER_IMAGE} {pytest_cmd}"
    )

    print(f"Running: {pytest_cmd}")
    result = c.run(cmd, pty=True, warn=True)
    if result.exited != 0:
        sys.exit(result.exited)
    print("\n✅ All tests passed!")


@task
def run(
    c: Context,
    campaign: str = "default",
    port: int = DEFAULT_PORT,
    detach: bool = False,
    dev: bool = False,
    model_file: str = "Qwen2.5-7B-Instruct-Q6_K_L.gguf",
) -> None:
    """
    Run the container (GPU-only). MODEL_FILE must exist under shared/models.
    """
    print_header(f"Starting Campaign: {campaign}")

    if not c.run(f'{DOCKER} images -q {DOCKER_IMAGE}', hide=True).stdout.strip():
        print("Image not found. Building first...")
        build(c)

    campaign_path = CAMPAIGN_DATA_PATH / "campaigns" / campaign
    shared_path = CAMPAIGN_DATA_PATH / "shared"
    (campaign_path).mkdir(parents=True, exist_ok=True)
    (shared_path / "models").mkdir(parents=True, exist_ok=True)

    model_host = shared_path / "models" / model_file
    if not model_host.exists():
        print(f"❌ MODEL_FILE not found: {model_host}")
        sys.exit(1)

    # Stop any existing container
    stop(c, quiet=True)

    detach_flag = "-d" if detach else "-it"

    cmd = (
        f"{DOCKER} run "
        f"{detach_flag} --rm "
        f"--name {CONTAINER_NAME} "
        f"-p {port}:{port} "
        f"--gpus all "
        f"-e NVIDIA_VISIBLE_DEVICES=all "
        f"-e NVIDIA_DRIVER_CAPABILITIES=compute,utility "
        f"-v {campaign_path}:/app/campaign-data "
        f"-v {shared_path}/pf2e.db:/app/data/pf2e.db:ro "
        f"-v {shared_path}/models:/app/models:ro "
        + (f"-v {PROJECT_ROOT}/src:/app/src:ro " if dev else "")
        +
        f"-e CAMPAIGN_NAME={campaign} "
        f"-e PORT={port} "
        "-e PYTHONPATH=/app "
        "-e CAMPAIGN_DATA_PATH=/app/campaign-data "
        "-e MODEL_PATH=/app/models "
        "-e PF2E_DB_PATH=/app/data/pf2e.db "
        f"-e MODEL_FILE=/app/models/{model_file} "
        f"{DOCKER_IMAGE}"
    )

    print(f"Starting container: {CONTAINER_NAME}")
    print(f"Campaign data: {campaign_path}")
    print(f"Model: {model_file}")
    print(f"Web UI: http://localhost:{port}")
    
    if detach:
        r = c.run(cmd, pty=False, warn=True)
        if r.exited == 0:
            print("\n✅ Container started in background")
            print("   View logs: invoke logs")
            print("   Stop: invoke stop")
    else:
        print("\nPress Ctrl+C to stop the container")
        c.run(cmd, pty=True)


@task
def stop(c: Context, quiet: bool = False) -> None:
    """
    Stop the running campaign container.

    Args:
        c: Invoke context
        quiet: Suppress output
    """
    if not quiet:
        print_header("Stopping Container")

    # Check if container is running
    result = c.run(f"{DOCKER} ps -q -f name={CONTAINER_NAME}", hide=True)

    if result.stdout.strip():
        c.run(f"{DOCKER} stop {CONTAINER_NAME}", hide=not quiet, warn=True)
        if not quiet:
            print(f"✅ Stopped {CONTAINER_NAME}")
    else:
        if not quiet:
            print(f"Container {CONTAINER_NAME} is not running")


@task
def logs(c: Context, follow: bool = False, lines: int = 50) -> None:
    """
    View container logs.

    Args:
        c: Invoke context
        follow: Follow log output
        lines: Number of lines to show
    """
    print_header("Container Logs")

    # Check if container exists
    result = c.run(f"{DOCKER} ps -a -q -f name={CONTAINER_NAME}", hide=True)

    if not result.stdout.strip():
        print(f"Container {CONTAINER_NAME} does not exist")
        return

    follow_flag = "-f" if follow else ""
    cmd = f"{DOCKER} logs {follow_flag} --tail {lines} {CONTAINER_NAME}"

    if follow:
        print("Following logs (Ctrl+C to exit)...")

    c.run(cmd, pty=True)


@task
def shell(c: Context, campaign: str = "default") -> None:
    """
    Open a shell inside the running container.

    Args:
        c: Invoke context
        campaign: Campaign name (for starting container if needed)
    """
    print_header("Container Shell")

    # Check if container is running
    result = c.run(f"{DOCKER} ps -q -f name={CONTAINER_NAME}", hide=True)

    if not result.stdout.strip():
        print(f"Container not running. Starting it first...")
        run(c, campaign=campaign, detach=True)

    print("Opening shell in container (type 'exit' to leave)")
    c.run(f"{DOCKER} exec -it {CONTAINER_NAME} /bin/bash", pty=True)


@task
def clean(c: Context, all_images: bool = False) -> None:
    """
    Clean up Docker resources.

    Args:
        c: Invoke context
        all_images: Remove all project images (not just latest)
    """
    print_header("Cleaning Docker Resources")

    # Stop container if running
    stop(c, quiet=True)

    # Remove project images
    if all_images:
        print("Removing all project images...")
        c.run(f"{DOCKER} rmi -f $({DOCKER} images '{PROJECT_NAME}*' -q)", warn=True)
    else:
        print(f"Removing image: {DOCKER_IMAGE}")
        c.run(f"{DOCKER} rmi -f {DOCKER_IMAGE}", warn=True)

    # Clean up dangling images
    print("Cleaning up dangling images...")
    c.run(f"{DOCKER} image prune -f", warn=True)

    print("✅ Cleanup complete")


@task
def status(c: Context) -> None:
    """
    Show status of containers and images.

    Args:
        c: Invoke context
    """
    print_header("Docker Status")

    print("📦 Project Images:")
    c.run(f"{DOCKER} images '{PROJECT_NAME}*'", pty=True)

    print("\n🏃 Running Containers:")
    result = c.run(f"{DOCKER} ps -f name={CONTAINER_NAME}", pty=True, warn=True)

    print("\n📁 Campaign Data:")
    if CAMPAIGN_DATA_PATH.exists():
        campaigns = list((CAMPAIGN_DATA_PATH / "campaigns").glob("*/"))
        if campaigns:
            for campaign_dir in campaigns:
                size = sum(f.stat().st_size for f in campaign_dir.rglob("*") if f.is_file())
                print(f"  - {campaign_dir.name}: {size / 1024 / 1024:.2f} MB")
        else:
            print("  No campaigns found")
    else:
        print(f"  Campaign directory not found: {CAMPAIGN_DATA_PATH}")

    print("\n🤖 Models:")
    models_path = CAMPAIGN_DATA_PATH / "shared" / "models"
    if models_path.exists():
        models = list(models_path.glob("*.gguf"))
        if models:
            for model_file in models:
                size = model_file.stat().st_size / 1024 / 1024 / 1024
                print(f"  - {model_file.name}: {size:.2f} GB")
        else:
            print("  No models found")
    else:
        print(f"  Models directory not found: {models_path}")


@task
def gpu_check(c: Context) -> None:
    """
    Check GPU availability and CUDA status in the container.
    """
    print_header("GPU/CUDA Status Check")

    # Check if image exists
    if not c.run(f'{DOCKER} images -q {DOCKER_IMAGE}', hide=True).stdout.strip():
        print("Image not found. Building first...")
        build(c)

    print("Checking CUDA availability in container...\n")

    # Python script to check GPU
    check_script = """
import sys
print("Python:", sys.version)
print()

# Check for CUDA via nvidia-smi
import subprocess
try:
    result = subprocess.run(['nvidia-smi'], capture_output=True, text=True)
    print("NVIDIA-SMI Output:")
    print(result.stdout)
except Exception as e:
    print(f"nvidia-smi not available: {e}")

print("-" * 60)

# Check llama-cpp-python CUDA support
try:
    import llama_cpp
    print("✅ llama-cpp-python imported successfully")
    print(f"   Version: {llama_cpp.__version__ if hasattr(llama_cpp, '__version__') else 'unknown'}")
    
    # Try to check CUDA availability
    try:
        # This will fail if no CUDA support, but that's OK
        model = llama_cpp.Llama(
            model_path="/dev/null",  # Dummy path
            n_gpu_layers=1,
            verbose=False
        )
    except Exception as init_error:
        # Check if error mentions CUDA
        if "CUDA" in str(init_error) or "GPU" in str(init_error):
            print("   CUDA mentioned in init - likely compiled with CUDA support")
        else:
            print(f"   Init test result: {init_error}")
    
except ImportError as e:
    print(f"❌ Failed to import llama-cpp-python: {e}")
"""

    cmd = (
        f"{DOCKER} run --rm "
        f"--gpus all "
        f"-e NVIDIA_VISIBLE_DEVICES=all "
        f"-e NVIDIA_DRIVER_CAPABILITIES=compute,utility "
        f"{DOCKER_IMAGE} "
        f'python3 -c "{check_script}"'
    )

    c.run(cmd, pty=True)


@task(help={
    'list': 'List all available tasks',
    'verbose': 'Show detailed task descriptions'
})
def help(c: Context, list: bool = False, verbose: bool = False) -> None:
    """
    Show help information for available tasks.

    Args:
        c: Invoke context
        list: List all tasks
        verbose: Show detailed descriptions
    """
    print_header("PF2e Society Scribe - Docker Tasks")

    if list or verbose:
        c.run("invoke --list", pty=True)
    else:
        print("Common commands:")
        print("  invoke build         - Build Docker image with GPU support")
        print("  invoke test          - Run tests in container")
        print("  invoke run           - Start campaign container")
        print("  invoke stop          - Stop running container")
        print("  invoke logs          - View container logs")
        print("  invoke shell         - Open shell in container")
        print("  invoke status        - Show Docker status")
        print("  invoke gpu-check     - Check GPU/CUDA availability")
        print("  invoke clean         - Clean up resources")
        print("\nFor more options: invoke --help [command]")
        print("List all tasks: invoke help --list")


# Alias common tasks for convenience
@task
def up(c: Context, campaign: str = "default") -> None:
    """Alias for 'run' - start the campaign container."""
    run(c, campaign=campaign)


@task
def down(c: Context) -> None:
    """Alias for 'stop' - stop the campaign container."""
    stop(c)