from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .compiler import CompilationError, CompilationTimeout, binary_path, compile_code
from .executor import run_testcase
from .models import (
    CompileRequest,
    CompileResponse,
    ExecuteRequest,
    ExecuteResponse,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="codebrownie judge", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/compile", response_model=CompileResponse)
async def compile_endpoint(req: CompileRequest):
    """
    Compiles C++23 source code.
    Returns a binary_id valid for /execute.
    Fails with 408 if compilation exceeds 30s, 422 on compiler error.
    """
    try:
        binary_id, warnings = await compile_code(req.code)
    except CompilationTimeout:
        raise HTTPException(
            status_code=408,
            detail={
                "error": "compilation_timeout",
                "message": "Compilation exceeded the 30 second limit.",
            },
        )
    except CompilationError as e:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "compilation_failed",
                "stderr": e.stderr,
            },
        )
    return CompileResponse(binary_id=binary_id, warnings=warnings)


@app.post("/execute", response_model=ExecuteResponse)
async def execute_endpoint(req: ExecuteRequest):
    """
    Executes a compiled binary against test cases.
    Returns per-case verdict: AC | TLE | MLE | RTE.
    """
    path = binary_path(req.binary_id)
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail={"error": "binary_not_found", "message": "Binary expired or never compiled."},
        )

    test_cases = req.test_cases if req.test_cases else [None]
    results: dict = {}
    counts = {"ac": 0, "tle": 0, "mle": 0, "rte": 0, "wa": 0}

    for i, tc in enumerate(test_cases):
        label = "default" if tc is None else str(i + 1)
        input_data = "" if tc is None else tc.input

        result = await run_testcase(
            binary=path,
            input_data=input_data,
            time_limit=req.time_limit,
            memory_limit_mb=req.memory_limit_mb,
        )

        # WA check if expected output provided
        if tc and tc.expected is not None and result.status == "AC":
            if result.stdout.strip() != tc.expected.strip():
                result.status = "WA"

        results[label] = result
        counts[result.status.lower()] = counts.get(result.status.lower(), 0) + 1

    failed = [k for k, v in results.items() if v.status != "AC"]

    summary = {
        "total": len(results),
        **counts,
        "all_passed": len(failed) == 0,
        "failed_cases": failed,
    }

    return ExecuteResponse(results=results, summary=summary)
