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

# Directory structure
HOME_DIR = Path.home()
CAMPAIGN_DATA_PATH = HOME_DIR / "pf2e-campaigns"
MODELS_PATH = CAMPAIGN_DATA_PATH / "models"
TUTORIAL_PATH = CAMPAIGN_DATA_PATH / "tutorial"
PROJECT_ROOT = Path(__file__).parent.resolve()

# Use a single, configurable Docker command everywhere.
# If you need sudo, set: export DOCKER_CMD="sudo docker"
DOCKER = os.environ.get("DOCKER_CMD", "docker")

def print_header(message: str) -> None:
    """Print a formatted header message."""
    print("\n" + "=" * 60)
    print(f"  {message}")
    print("=" * 60 + "\n")


def ensure_directories() -> None:
    """Ensure required directories exist."""
    CAMPAIGN_DATA_PATH.mkdir(parents=True, exist_ok=True)
    MODELS_PATH.mkdir(parents=True, exist_ok=True)
    TUTORIAL_PATH.mkdir(parents=True, exist_ok=True)


@task
def setup(c: Context) -> None:
    """
    Initial setup - create directories and tutorial data.
    """
    print_header("Setting up PF2e Society Scribe")
    
    ensure_directories()
    
    # Run tutorial setup if it exists and tutorial isn't set up
    if not (TUTORIAL_PATH / "characters").exists():
        setup_script = PROJECT_ROOT / "setup_tutorial.py"
        if setup_script.exists():
            print("📚 Setting up tutorial campaign...")
            c.run(f"{sys.executable} {setup_script}", pty=True)
        else:
            print("⚠️  setup_tutorial.py not found")
    
    print("\n✅ Setup complete!")
    print(f"📁 Campaign data: {CAMPAIGN_DATA_PATH}")
    print(f"📁 Models: {MODELS_PATH}")
    print(f"📁 Tutorial: {TUTORIAL_PATH}")
    
    # List available models
    models = list(MODELS_PATH.glob("*.gguf"))
    if models:
        print("\n📦 Available models:")
        for model in models:
            size_gb = model.stat().st_size / (1024**3)
            print(f"  - {model.name} ({size_gb:.2f} GB)")
    else:
        print("\n⚠️  No models found. Download GGUF models to:")
        print(f"   {MODELS_PATH}/")


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
    model_file: str = None,
) -> None:
    """
    Run pytest in the CUDA container.
    
    Args:
        c: Invoke context
        verbose: Verbose test output
        coverage: Generate coverage report
        model_file: GGUF model file name (must be in ~/pf2e-campaigns/models/)
    """
    print_header("Running Tests in Docker (GPU-only)")

    ensure_directories()

    # Ensure image exists
    if not c.run(f'{DOCKER} images -q {DOCKER_IMAGE}', hide=True).stdout.strip():
        print("Image not found. Building first...")
        build(c)

    # Find or validate model
    if model_file:
        model_path = MODELS_PATH / model_file
        if not model_path.exists():
            print(f"❌ Model not found: {model_path}")
            print(f"   Download your GGUF model to: {MODELS_PATH}/")
            available = list(MODELS_PATH.glob("*.gguf"))
            if available:
                print("\n   Available models:")
                for m in available:
                    print(f"     - {m.name}")
            sys.exit(1)
    else:
        # Try to find a model automatically
        available = list(MODELS_PATH.glob("*.gguf"))
        if available:
            model_file = available[0].name
            print(f"✓ Auto-selected model: {model_file}")
        else:
            print(f"❌ No GGUF models found in: {MODELS_PATH}/")
            print("   Download a model first or specify with --model-file")
            sys.exit(1)

    # pytest cmd
    pytest_cmd = "pytest"
    if verbose:
        pytest_cmd += " -v"
    if coverage:
        pytest_cmd += " --cov=src --cov-report=term-missing --cov-report=html"

    # GPU configuration
    gpu_bits = "--gpus all -e NVIDIA_VISIBLE_DEVICES=all -e NVIDIA_DRIVER_CAPABILITIES=compute,utility"

    env_vars = (
        "-e PYTHONPATH=/app "
        f"-e CAMPAIGN_DATA_PATH=/campaign-data "
        f"-e MODEL_PATH=/models "
        f"-e MODEL_FILE={model_file} "
        "-e PF2E_DB_PATH=/app/data/pf2e.db "
        "-e PORT=8000 "
    )

    cmd = (
        f"sudo {DOCKER} run --rm {gpu_bits} "
        f"-v {PROJECT_ROOT}/tests:/app/tests:ro "
        f"-v {PROJECT_ROOT}/src:/app/src:ro "
        f"-v {CAMPAIGN_DATA_PATH}:/campaign-data "
        f"-v {MODELS_PATH}:/models:ro "
        f"{env_vars}"
        f"{DOCKER_IMAGE} {pytest_cmd}"
    )

    print(f"Running: {pytest_cmd}")
    print(f"Model: {model_file}")
    result = c.run(cmd, pty=True, warn=True)
    if result.exited != 0:
        sys.exit(result.exited)
    print("\n✅ All tests passed!")


@task
def run(
    c: Context,
    campaign: str = "tutorial",
    port: int = DEFAULT_PORT,
    detach: bool = False,
    dev: bool = False,
    model_file: str = None,
) -> None:
    """
    Run the container (GPU-only).
    
    Args:
        c: Invoke context
        campaign: Campaign name (default: tutorial)
        port: Port to expose
        detach: Run in background
        dev: Development mode (mount src directory)
        model_file: GGUF model file name
    """
    print_header(f"Starting Campaign: {campaign}")

    ensure_directories()

    if not c.run(f'{DOCKER} images -q {DOCKER_IMAGE}', hide=True).stdout.strip():
        print("Image not found. Building first...")
        build(c)

    # Find or validate model
    if model_file:
        model_path = MODELS_PATH / model_file
        if not model_path.exists():
            print(f"❌ Model not found: {model_path}")
            sys.exit(1)
    else:
        available = list(MODELS_PATH.glob("*.gguf"))
        if available:
            model_file = available[0].name
            print(f"✓ Using model: {model_file}")
        else:
            print(f"❌ No models found in: {MODELS_PATH}/")
            sys.exit(1)

    campaign_path = CAMPAIGN_DATA_PATH / campaign

    # Stop any existing container
    stop(c, quiet=True)

    detach_flag = "-d" if detach else "-it"

    cmd = (
        f"sudo {DOCKER} run "
        f"{detach_flag} --rm "
        f"--name {CONTAINER_NAME} "
        f"-p {port}:{port} "
        f"--gpus all "
        f"-e NVIDIA_VISIBLE_DEVICES=all "
        f"-e NVIDIA_DRIVER_CAPABILITIES=compute,utility "
        f"-v {campaign_path}:/app/campaign-data "
        f"-v {MODELS_PATH}:/models:ro "
        + (f"-v {PROJECT_ROOT}/src:/app/src:ro " if dev else "")
        + f"-e CAMPAIGN_NAME={campaign} "
        f"-e PORT={port} "
        "-e PYTHONPATH=/app "
        "-e CAMPAIGN_DATA_PATH=/app/campaign-data "
        "-e MODEL_PATH=/models "
        f"-e MODEL_FILE={model_file} "
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
        c.run(f"sudo {DOCKER} stop {CONTAINER_NAME}", hide=not quiet, warn=True)
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
def shell(c: Context, campaign: str = "tutorial") -> None:
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
    c.run(f"sudo {DOCKER} exec -it {CONTAINER_NAME} /bin/bash", pty=True)


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
        c.run(f"sudo {DOCKER} rmi -f $(sudo {DOCKER} images '{PROJECT_NAME}*' -q)", warn=True)
    else:
        print(f"Removing image: {DOCKER_IMAGE}")
        c.run(f"sudo {DOCKER} rmi -f {DOCKER_IMAGE}", warn=True)

    # Clean up dangling images
    print("Cleaning up dangling images...")
    c.run(f"sudo {DOCKER} image prune -f", warn=True)

    print("✅ Cleanup complete")


@task
def status(c: Context) -> None:
    """
    Show status of containers, images, and data.

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
        campaigns = [d for d in CAMPAIGN_DATA_PATH.iterdir() if d.is_dir() and d.name != "models"]
        if campaigns:
            for campaign_dir in campaigns:
                size = sum(f.stat().st_size for f in campaign_dir.rglob("*") if f.is_file())
                print(f"  - {campaign_dir.name}: {size / 1024 / 1024:.2f} MB")
        else:
            print("  No campaigns found")
    else:
        print(f"  Campaign directory not found: {CAMPAIGN_DATA_PATH}")

    print("\n🤖 Models:")
    if MODELS_PATH.exists():
        models = list(MODELS_PATH.glob("*.gguf"))
        if models:
            for model_file in models:
                size = model_file.stat().st_size / 1024 / 1024 / 1024
                print(f"  - {model_file.name}: {size:.2f} GB")
        else:
            print("  No models found")
            print(f"  Download models to: {MODELS_PATH}/")
    else:
        print(f"  Models directory not found: {MODELS_PATH}")



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
        print("Setup:")
        print(f"  invoke setup         - Initial setup (creates {CAMPAIGN_DATA_PATH})")
        print("  invoke download-model --url=<url>  - Download GGUF model")
        print()
        print("Docker commands:")
        print("  invoke build         - Build Docker image with GPU support")
        print("  invoke test          - Run tests in container")
        print("  invoke run           - Start campaign container")
        print("  invoke stop          - Stop running container")
        print("  invoke logs          - View container logs")
        print("  invoke shell         - Open shell in container")
        print("  invoke status        - Show Docker status")
        print("  invoke gpu-check     - Check GPU/CUDA availability")
        print("  invoke clean         - Clean up resources")
        print()
        print(f"Models directory: {MODELS_PATH}/")
        print(f"Campaign data: {CAMPAIGN_DATA_PATH}/")
        print("\nFor more options: invoke --help [command]")
        print("List all tasks: invoke help --list")


# Alias common tasks for convenience
@task
def up(c: Context, campaign: str = "tutorial") -> None:
    """Alias for 'run' - start the campaign container."""
    run(c, campaign=campaign)


@task
def down(c: Context) -> None:
    """Alias for 'stop' - stop the campaign container."""
    stop(c)