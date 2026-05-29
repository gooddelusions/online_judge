"""
Judge service tests — run with: poetry run python tests/test_judge.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.judge.compiler import (
    CompilationError,
    binary_path,
    compile_code,
)
from services.judge.executor import run_testcase

GREEN = "\033[92m"
RED   = "\033[91m"
DIM   = "\033[2m"
RESET = "\033[0m"
BOLD  = "\033[1m"

passed = []
failed = []


async def run(label: str, coro):
    try:
        await coro
        print(f"  {GREEN}✓{RESET} {label}")
        passed.append(label)
    except AssertionError as e:
        print(f"  {RED}✗{RESET} {label}: {RED}{e}{RESET}")
        failed.append(label)
    except Exception as e:
        print(f"  {RED}✗{RESET} {label}: {RED}{type(e).__name__}: {e}{RESET}")
        failed.append(label)


# ─── helpers ────────────────────────────────────────────────────────────────

async def compile(code: str) -> str:
    bid, _ = await compile_code(code)
    return bid


async def execute(bid: str, inp="", time_limit=5.0, mem=200):
    return await run_testcase(binary_path(bid), inp, time_limit, mem)


# ─── Compiler ────────────────────────────────────────────────────────────────

async def test_compile_success():
    bid = await compile('#include<iostream>\nint main(){std::cout<<"ok";}')
    assert bid, "binary_id empty"
    assert binary_path(bid).exists(), "binary not on disk"


async def test_compile_error():
    try:
        await compile_code("int main() { undeclared_var; }")
        assert False, "should raise"
    except CompilationError as e:
        assert e.stderr, "stderr empty on compile error"
        assert "error" in e.stderr.lower()


async def test_compile_empty_code():
    try:
        await compile_code("")
        assert False, "should raise"
    except CompilationError:
        pass


async def test_compile_cpp23_print():
    bid = await compile('#include<print>\nint main(){ std::print("{}\\n", 42); }')
    assert binary_path(bid).exists()


async def test_compile_bits_stdc():
    bid = await compile(
        "#include<bits/stdc++.h>\nusing namespace std;\nint main(){cout<<\"ok\";}"
    )
    assert binary_path(bid).exists()


async def test_compile_warnings_non_fatal():
    code = """
#include<iostream>
int main() {
    int x;          // uninitialized — may warn but not error
    std::cout << 1;
}
"""
    bid, warnings = await compile_code(code)
    assert binary_path(bid).exists(), "binary missing despite valid code"


# ─── Executor ────────────────────────────────────────────────────────────────

async def test_ac_with_input():
    bid = await compile(
        "#include<bits/stdc++.h>\nusing namespace std;\n"
        "int main(){int n;cin>>n;cout<<n*2;}"
    )
    r = await execute(bid, "21")
    assert r.status == "AC", f"got {r.status}"
    assert r.stdout.strip() == "42", f"got {repr(r.stdout)}"
    assert r.time_ms < 1000


async def test_ac_no_input():
    bid = await compile('#include<iostream>\nint main(){std::cout<<"hello world";}')
    r = await execute(bid, "")
    assert r.status == "AC"
    assert "hello world" in r.stdout


async def test_ac_multiple_lines_output():
    bid = await compile("""
#include<iostream>
using namespace std;
int main(){for(int i=1;i<=5;i++) cout<<i<<"\\n";}
""")
    r = await execute(bid)
    assert r.status == "AC"
    assert r.stdout.strip() == "1\n2\n3\n4\n5"


async def test_tle_infinite_loop():
    bid = await compile("int main(){while(1){}}")
    r = await execute(bid, "", time_limit=1.0)
    assert r.status == "TLE", f"got {r.status}"
    assert r.time_ms >= 1000


async def test_tle_reports_correct_time():
    bid = await compile("int main(){while(1){}}")
    r = await execute(bid, "", time_limit=2.0)
    assert r.status == "TLE"
    assert 1900 <= r.time_ms <= 2500, f"time {r.time_ms}ms unexpected"


async def test_mle_unbounded_alloc():
    bid = await compile("""
#include<vector>
int main(){
    std::vector<int> v;
    while(true) v.resize(v.size()+5000000,1);
}
""")
    r = await execute(bid, "", time_limit=5.0, mem=32)
    assert r.status == "MLE", f"got {r.status} (mem={r.memory_mb:.1f}MB)"


async def test_rte_segfault():
    bid = await compile("int main(){int*p=nullptr;*p=1;}")
    r = await execute(bid)
    assert r.status in ("RTE", "MLE"), f"got {r.status}"


async def test_rte_nonzero_exit():
    bid = await compile("int main(){return 42;}")
    r = await execute(bid)
    assert r.status == "RTE", f"got {r.status}"


async def test_rte_throw_uncaught():
    bid = await compile('#include<stdexcept>\nint main(){throw std::runtime_error("boom");}')
    r = await execute(bid)
    assert r.status == "RTE"


async def test_stderr_captured():
    bid = await compile("""
#include<iostream>
int main(){
    std::cerr<<"err_msg";
    std::cout<<"out_msg";
}
""")
    r = await execute(bid)
    assert r.status == "AC"
    assert "out_msg" in r.stdout
    assert "err_msg" in r.stderr


async def test_memory_reported_nonzero():
    bid = await compile('#include<iostream>\nint main(){std::cout<<1;}')
    r = await execute(bid)
    assert r.memory_mb > 0, "memory should be non-zero"


async def test_time_reported_nonzero():
    bid = await compile('#include<iostream>\nint main(){std::cout<<1;}')
    r = await execute(bid)
    assert r.time_ms > 0, "time should be non-zero"


async def test_multi_inputs_sequential():
    bid = await compile(
        "#include<bits/stdc++.h>\nusing namespace std;\n"
        "int main(){int n;cin>>n;cout<<n*n;}"
    )
    expected = {"2": "4", "3": "9", "5": "25", "10": "100"}
    for inp, want in expected.items():
        r = await execute(bid, inp)
        assert r.status == "AC" and r.stdout.strip() == want, \
            f"input={inp}: got {repr(r.stdout)} want {want}"


async def test_large_output_truncated():
    # prints 2MB+ of data — should be capped at 1MB
    bid = await compile("""
#include<iostream>
#include<string>
int main(){
    std::string line(1000,'x');
    for(int i=0;i<3000;i++) std::cout<<line<<"\\n";
}
""")
    r = await execute(bid)
    assert r.status == "AC"
    assert len(r.stdout) <= 1 * 1024 * 1024 + 100, "output exceeds cap"


# ─── Main ────────────────────────────────────────────────────────────────────

async def main():
    compiler_tests = [
        ("compile: success",               test_compile_success()),
        ("compile: error reported",        test_compile_error()),
        ("compile: empty code → error",    test_compile_empty_code()),
        ("compile: C++23 std::print",      test_compile_cpp23_print()),
        ("compile: bits/stdc++.h",         test_compile_bits_stdc()),
        ("compile: warnings non-fatal",    test_compile_warnings_non_fatal()),
    ]

    executor_tests = [
        ("execute: AC with input",             test_ac_with_input()),
        ("execute: AC no input",               test_ac_no_input()),
        ("execute: AC multi-line output",      test_ac_multiple_lines_output()),
        ("execute: TLE infinite loop",         test_tle_infinite_loop()),
        ("execute: TLE time reported",         test_tle_reports_correct_time()),
        ("execute: MLE unbounded alloc",       test_mle_unbounded_alloc()),
        ("execute: RTE segfault",              test_rte_segfault()),
        ("execute: RTE non-zero exit",         test_rte_nonzero_exit()),
        ("execute: RTE uncaught exception",    test_rte_throw_uncaught()),
        ("execute: stderr captured",           test_stderr_captured()),
        ("execute: memory reported",           test_memory_reported_nonzero()),
        ("execute: time reported",             test_time_reported_nonzero()),
        ("execute: multi-input correctness",   test_multi_inputs_sequential()),
        ("execute: large output capped",       test_large_output_truncated()),
    ]

    print(f"\n{BOLD}── Compiler ──────────────────────────────────{RESET}")
    for label, coro in compiler_tests:
        await run(label, coro)

    print(f"\n{BOLD}── Executor ──────────────────────────────────{RESET}")
    for label, coro in executor_tests:
        await run(label, coro)

    total = len(passed) + len(failed)
    color = GREEN if not failed else RED
    print(f"\n{BOLD}── Summary ───────────────────────────────────{RESET}")
    print(f"  {color}{len(passed)}/{total} passed{RESET}")
    if failed:
        print(f"\n  {RED}Failed:{RESET}")
        for f in failed:
            print(f"    • {f}")
        sys.exit(1)


asyncio.run(main())
