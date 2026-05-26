from agentcore.evidence import EvidenceLedger


def test_record_and_read_entries():
    ledger = EvidenceLedger()
    ledger.record("get_valuation", {"stock_no": "2330"}, {"pe": 22.5})

    entries = ledger.entries()
    assert len(entries) == 1
    assert entries[0].tool == "get_valuation"
    assert entries[0].args == {"stock_no": "2330"}
    assert entries[0].result == {"pe": 22.5}


def test_args_are_copied_not_referenced():
    ledger = EvidenceLedger()
    args = {"stock_no": "2330"}
    ledger.record("get_valuation", args, {"pe": 1})
    args["stock_no"] = "MUTATED"
    assert ledger.entries()[0].args == {"stock_no": "2330"}
