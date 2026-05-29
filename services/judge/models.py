from pydantic import BaseModel, Field


class CompileRequest(BaseModel):
    code: str


class CompileResponse(BaseModel):
    binary_id: str
    warnings: str = ""


class TestCase(BaseModel):
    input: str = ""
    expected: str | None = None


class ExecuteRequest(BaseModel):
    binary_id: str
    time_limit: float = Field(default=10.0, gt=0, le=60)
    memory_limit_mb: int = Field(default=200, gt=0, le=1024)
    test_cases: list[TestCase] = []


class CaseResult(BaseModel):
    status: str  # AC | WA | TLE | MLE | RTE
    time_ms: float
    memory_mb: float
    stdout: str
    stderr: str


class ExecuteResponse(BaseModel):
    results: dict[str, CaseResult]
    summary: dict
