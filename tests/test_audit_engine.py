from pathlib import Path

from dimcause.audit.engine import AuditEngine, BaseCheck, CheckResult


class MockCheck(BaseCheck):
    name = "mock"

    def run(self, files):
        return CheckResult(self.name, True, "Mock passed")


class CrashCheck(BaseCheck):
    name = "crash"

    def run(self, files):
        raise ValueError("Boom")


def test_engine_registration():
    engine = AuditEngine()
    check = MockCheck()
    engine.register(check)
    assert len(engine._checks) == 1
    assert engine._checks[0] == check


def test_engine_run_success():
    engine = AuditEngine()
    engine.register(MockCheck())
    results = engine.run_all([Path("test.py")], parallel=False)
    assert len(results) == 1
    assert results[0].success
    assert results[0].check_name == "mock"


def test_engine_run_crash_handling():
    engine = AuditEngine()
    engine.register(CrashCheck())
    results = engine.run_all([Path("test.py")], parallel=False)
    assert len(results) == 1
    assert not results[0].success
    assert "Crashed" in results[0].message


def test_engine_parallel_execution():
    engine = AuditEngine()
    engine.register(MockCheck())
    engine.register(MockCheck())
    results = engine.run_all([Path("test.py")], parallel=True)
    assert len(results) == 2
    assert all(r.success for r in results)
