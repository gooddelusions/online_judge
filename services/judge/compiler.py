import asyncio
import tempfile
import uuid
from pathlib import Path

BINARY_DIR = Path(tempfile.gettempdir()) / "cb_judge_binaries"
BINARY_DIR.mkdir(exist_ok=True)

COMPILE_TIMEOUT = 30
CPP_FLAGS = ["-O2", "-std=c++23", "-DONLINE_JUDGE"]
OUTPUT_CAP = 1 * 1024 * 1024  # 1 MB


class CompilationError(Exception):
    def __init__(self, stderr: str):
        self.stderr = stderr


class CompilationTimeout(Exception):
    pass


async def compile_code(code: str) -> tuple[str, str]:
    """
    Compiles C++ source. Returns (binary_id, warnings).
    Raises CompilationError or CompilationTimeout.
    """
    binary_id = str(uuid.uuid4())
    binary_path = BINARY_DIR / binary_id

    with tempfile.NamedTemporaryFile(suffix=".cpp", mode="w", delete=False) as f:
        f.write(code)
        src_path = Path(f.name)

    try:
        proc = await asyncio.create_subprocess_exec(
            "g++", *CPP_FLAGS, "-o", str(binary_path), str(src_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=COMPILE_TIMEOUT
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise CompilationTimeout()

        stderr_text = stderr.decode(errors="replace")[:OUTPUT_CAP]

        if proc.returncode != 0:
            raise CompilationError(stderr_text)

        binary_path.chmod(0o755)
        return binary_id, stderr_text

    finally:
        src_path.unlink(missing_ok=True)


def binary_path(binary_id: str) -> Path:
    return BINARY_DIR / binary_id
