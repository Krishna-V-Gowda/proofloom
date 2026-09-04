from copy import deepcopy

from proofloom.audit import AuditLedger, simulate_tamper


def _ledger():
    ledger = AuditLedger()
    ledger.append("one", "system", "corr", {"value": [1, 2]})
    ledger.append("two", "human", "corr", {"approved": True})
    ledger.append("three", "system", "corr", {"status": "done"})
    return ledger


def test_payload_is_owned_and_chain_valid():
    payload = {"values": [1]}
    ledger = AuditLedger()
    ledger.append("created", "system", "corr", payload)
    payload["values"].append(2)
    assert ledger.verify().valid
    assert ledger.entries[0].payload["values"] == [1]


def test_mutation_deletion_insertion_reordering_and_truncation_are_bounded():
    ledger = _ledger()
    assert ledger.verify().valid
    assert not ledger.verify(simulate_tamper(ledger.entries, 2, "changed", True)).valid
    exported = ledger.export()
    assert not ledger.verify(exported[:1] + exported[2:]).valid
    inserted = deepcopy(exported)
    inserted.insert(1, deepcopy(exported[0]))
    assert not ledger.verify(inserted).valid
    reordered = [exported[1], exported[0], exported[2]]
    assert not ledger.verify(reordered).valid
    # Truncation is internally valid but produces a different head. This is why
    # a production ledger needs durable retention/external anchoring.
    truncated = ledger.verify(exported[:-1])
    assert truncated.valid
    assert truncated.head_hash != ledger.head_hash
