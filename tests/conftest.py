"""tests/conftest.py — inject AlgorithmImports stubs and shared fixtures."""

import sys
import types
from datetime import datetime

import pytest

import type_stubs


def _inject_stub_module():
    stub_module = types.ModuleType("AlgorithmImports")
    for name in getattr(type_stubs, "__all__", dir(type_stubs)):
        if name.startswith("_"):
            continue
        setattr(stub_module, name, getattr(type_stubs, name))
    sys.modules["AlgorithmImports"] = stub_module


_inject_stub_module()


class _FakePortfolio:
    def __init__(self, value: float = 100_000.0):
        self.total_portfolio_value = value


class _FakeAlgo:
    def __init__(self):
        self.time = datetime(2024, 1, 15, 9, 35)
        self.portfolio = _FakePortfolio()
        self.securities = {}
        self.logs: list[str] = []

    def debug(self, msg):
        self.logs.append(str(msg))

    def log(self, msg):
        self.logs.append(str(msg))

    def error(self, msg):
        self.logs.append(str(msg))

    def history(self, *_a, **_k):
        return None


@pytest.fixture
def algo():
    return _FakeAlgo()
