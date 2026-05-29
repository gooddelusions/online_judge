import asyncio
import resource
import signal
import time
from pathlib import Path

import psutil

from .models import CaseResult

OUTPUT_CAP = 1 * 1024 * 1024       # 1 MB max stdout/stderr
MEM_POLL_INTERVAL = 0.05            # 50 ms
SHARED_LIB_OVERHEAD_MB = 100        # virtual address space buffer for glibc/runtime


def _apply_limits(memory_limit_mb: int, time_limit: float) -> None:
    """Runs in the child process before exec."""
    mem_bytes = (memory_limit_mb + SHARED_LIB_OVERHEAD_MB) * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS,    (mem_bytes, mem_bytes))
    resource.setrlimit(resource.RLIMIT_CPU,   (int(time_limit) + 2, int(time_limit) + 2))
    resource.setrlimit(resource.RLIMIT_FSIZE, (64 * 1024 * 1024, 64 * 1024 * 1024))  # 64 MB max file write
    resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))                               # no fork bombs


async def _monitor_memory(pid: int, stop: asyncio.Event) -> float:
    peak_mb = 0.0
    try:
        ps = psutil.Process(pid)
        while not stop.is_set():
            try:
                mem = ps.memory_info().rss / 1024 / 1024
                if mem > peak_mb:
                    peak_mb = mem
            except psutil.NoSuchProcess:
                break
            await asyncio.sleep(MEM_POLL_INTERVAL)
    except Exception:
        pass
    return peak_mb


async def run_testcase(
    binary: Path,
    input_data: str,
    time_limit: float,
    memory_limit_mb: int,
) -> CaseResult:
    preexec = lambda: _apply_limits(memory_limit_mb, time_limit)

    proc = await asyncio.create_subprocess_exec(
        str(binary),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        preexec_fn=preexec,
    )

    stop_monitor = asyncio.Event()
    monitor_task = asyncio.create_task(_monitor_memory(proc.pid, stop_monitor))
    start = time.perf_counter()

    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(input=input_data.encode()),
            timeout=time_limit,
        )
        elapsed_ms = (time.perf_counter() - start) * 1000

    except asyncio.TimeoutError:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        await proc.wait()
        elapsed_ms = time_limit * 1000
        stop_monitor.set()
        peak_mb = await monitor_task
        return CaseResult(
            status="TLE",
            time_ms=round(elapsed_ms, 2),
            memory_mb=round(peak_mb, 2),
            stdout="",
            stderr=f"Time limit exceeded ({time_limit}s)",
        )

    stop_monitor.set()
    peak_mb = await monitor_task

    stdout = stdout_bytes.decode(errors="replace")[:OUTPUT_CAP]
    stderr = stderr_bytes.decode(errors="replace")[:OUTPUT_CAP]
    rc = proc.returncode

    # Classify verdict
    if rc == 0:
        status = "AC"
    elif rc < 0:
        # Killed by signal — MLE if peak RSS is close to the limit, else RTE
        sig = -rc
        if peak_mb >= memory_limit_mb * 0.9 or sig == signal.SIGSEGV and peak_mb > memory_limit_mb * 0.5:
            status = "MLE"
        else:
            sig_name = signal.Signals(sig).name if sig in signal.Signals._value2member_map_ else f"SIG{sig}"
            status = "RTE"
            stderr = stderr or f"Runtime error — killed by {sig_name}"
    else:
        status = "RTE"
        stderr = stderr or f"Non-zero exit code: {rc}"

    return CaseResult(
        status=status,
        time_ms=round(elapsed_ms, 2),
        memory_mb=round(peak_mb, 2),
        stdout=stdout,
        stderr=stderr,
    )
