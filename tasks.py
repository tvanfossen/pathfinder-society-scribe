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


def print_header(message: str) -> None:
    """Print a formatted header message."""
    print("\n" + "=" * 60)
    print(f"  {message}")
    print("=" * 60 + "\n")


@task
def build(c: Context, no_cache: bool = False) -> None:
    """
    Build the Docker image for the society scribe.
    
    Args:
        c: Invoke context
        no_cache: Build without using cache
    """
    print_header("Building Docker Image")
    
    cache_flag = "--no-cache" if no_cache else ""
    cmd = f"sudo docker build {cache_flag} -t {DOCKER_IMAGE} ."
    
    print(f"Building image: {DOCKER_IMAGE}")
    print(f"Command: {cmd}")
    
    result = c.run(cmd, pty=True, warn=True)
    
    if result.exited == 0:
        print(f"\n✅ Successfully built {DOCKER_IMAGE}")
        # Show image info
        c.run(f"docker images {DOCKER_IMAGE}", pty=True)
    else:
        print(f"\n❌ Build failed with exit code {result.exited}")
        sys.exit(1)


@task
def test(c: Context, verbose: bool = False, coverage: bool = True) -> None:
    """
    Run pytest tests inside the Docker container.
    
    Args:
        c: Invoke context
        verbose: Run tests in verbose mode
        coverage: Generate coverage report
    """
    print_header("Running Tests in Docker")
    
    # Ensure image is built
    result = c.run(f"docker images -q {DOCKER_IMAGE}", hide=True)
    if not result.stdout.strip():
        print("Image not found. Building first...")
        build(c)
    
    # Prepare pytest command
    pytest_cmd = "pytest"
    if verbose:
        pytest_cmd += " -v"
    if coverage:
        pytest_cmd += " --cov=src --cov-report=term-missing --cov-report=html"
    
    # Run tests in container
    cmd = (
        f"docker run --rm "
        f"-v {PROJECT_ROOT}/tests:/app/tests:ro "
        f"-v {PROJECT_ROOT}/src:/app/src:ro "
        f"-e PYTHONPATH=/app "
        f"{DOCKER_IMAGE} "
        f"{pytest_cmd}"
    )
    
    print(f"Running: {pytest_cmd}")
    result = c.run(cmd, pty=True, warn=True)
    
    if result.exited == 0:
        print("\n✅ All tests passed!")
    else:
        print(f"\n❌ Tests failed with exit code {result.exited}")
        sys.exit(1)


@task
def run(
    c: Context,
    campaign: str = "default",
    port: int = DEFAULT_PORT,
    detach: bool = False,
    dev: bool = False
) -> None:
    """
    Run the society scribe container.
    
    Args:
        c: Invoke context
        campaign: Campaign name to load
        port: Port to expose for web UI
        detach: Run container in background
        dev: Run in development mode with live code mounting
    """
    print_header(f"Starting Campaign: {campaign}")
    
    # Ensure image is built
    result = c.run(f"docker images -q {DOCKER_IMAGE}", hide=True)
    if not result.stdout.strip():
        print("Image not found. Building first...")
        build(c)
    
    # Setup campaign data directory
    campaign_path = CAMPAIGN_DATA_PATH / "campaigns" / campaign
    campaign_path.mkdir(parents=True, exist_ok=True)
    
    shared_path = CAMPAIGN_DATA_PATH / "shared"
    shared_path.mkdir(parents=True, exist_ok=True)
    
    # Check for pf2e.db
    pf2e_db_path = shared_path / "pf2e.db"
    if not pf2e_db_path.exists():
        print(f"⚠️  Warning: pf2e.db not found at {pf2e_db_path}")
        print("   Run 'invoke generate-rules-db' to create it (not yet implemented)")
    
    # Stop any existing container
    stop(c, quiet=True)
    
    # Build docker run command
    detach_flag = "-d" if detach else "-it"
    
    # Volume mounts
    volumes = [
        f"-v {campaign_path}:/app/campaign-data",
        f"-v {shared_path}/pf2e.db:/app/data/pf2e.db:ro",
        f"-v {shared_path}/models:/app/models:ro",
    ]
    
    # Development mode - mount source code
    if dev:
        volumes.append(f"-v {PROJECT_ROOT}/src:/app/src:ro")
        print("🔧 Development mode: mounting source code")
    
    # Environment variables
    env_vars = [
        f"-e CAMPAIGN_NAME={campaign}",
        f"-e PORT={port}",
    ]
    
    cmd = (
        f"docker run {detach_flag} --rm "
        f"--name {CONTAINER_NAME} "
        f"-p {port}:{port} "
        f"{' '.join(volumes)} "
        f"{' '.join(env_vars)} "
        f"{DOCKER_IMAGE}"
    )
    
    print(f"Starting container: {CONTAINER_NAME}")
    print(f"Campaign data: {campaign_path}")
    print(f"Web UI will be available at: http://localhost:{port}")
    
    if detach:
        result = c.run(cmd, pty=False, warn=True)
        if result.exited == 0:
            print(f"\n✅ Container started in background")
            print(f"   View logs: invoke logs")
            print(f"   Stop: invoke stop")
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
    result = c.run(f"docker ps -q -f name={CONTAINER_NAME}", hide=True)
    
    if result.stdout.strip():
        c.run(f"docker stop {CONTAINER_NAME}", hide=not quiet, warn=True)
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
    result = c.run(f"docker ps -a -q -f name={CONTAINER_NAME}", hide=True)
    
    if not result.stdout.strip():
        print(f"Container {CONTAINER_NAME} does not exist")
        return
    
    follow_flag = "-f" if follow else ""
    cmd = f"docker logs {follow_flag} --tail {lines} {CONTAINER_NAME}"
    
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
    result = c.run(f"docker ps -q -f name={CONTAINER_NAME}", hide=True)
    
    if not result.stdout.strip():
        print(f"Container not running. Starting it first...")
        run(c, campaign=campaign, detach=True)
    
    print("Opening shell in container (type 'exit' to leave)")
    c.run(f"docker exec -it {CONTAINER_NAME} /bin/bash", pty=True)


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
        c.run(f"docker rmi -f $(docker images '{PROJECT_NAME}*' -q)", warn=True)
    else:
        print(f"Removing image: {DOCKER_IMAGE}")
        c.run(f"docker rmi -f {DOCKER_IMAGE}", warn=True)
    
    # Clean up dangling images
    print("Cleaning up dangling images...")
    c.run("docker image prune -f", warn=True)
    
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
    c.run(f"docker images '{PROJECT_NAME}*'", pty=True)
    
    print("\n🏃 Running Containers:")
    result = c.run(f"docker ps -f name={CONTAINER_NAME}", pty=True, warn=True)
    
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
        print("  invoke build          - Build Docker image")
        print("  invoke test          - Run tests in container")
        print("  invoke run           - Start campaign container")
        print("  invoke stop          - Stop running container")
        print("  invoke logs          - View container logs")
        print("  invoke shell         - Open shell in container")
        print("  invoke status        - Show Docker status")
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