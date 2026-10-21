"""Phase 4: canonical records, Ed25519 signatures, the hash chain, the ledger and the edge runner.

Signatures and the chain protect records AFTER they are signed. These tests check that edits,
deletions, reordering and impersonation are found, and that tail truncation without an anchor is
NOT found. None of this covers a lie at the sensor before the device signs it.
"""

# ruff: noqa: E501
import hashlib
import io
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from edge.chain import (
    Anchor,
    ChainWriter,
    Entry,
    Ledger,
    Signer,
    build_record,
    canonical_bytes,
    default_key_dir,
    genesis_hash,
    link_hash,
    load_or_create_signer,
    make_anchor,
    new_run_id,
    parse_canonical,
    to_scaled_int,
    verify_chain,
    verify_signature,
)
from edge.chain.canonical import FIELDS, UNIT_E4, UNIT_E6, UNIT_E9, UNIT_MS
from edge.cli import main as edge_main
from edge.pi_source import PiSource
from edge.runner import DEFAULT_DEVICE_ID, run_recording
from edge.twin_cli import analyse

ROOT = Path(__file__).resolve().parent.parent
RECORDINGS = ROOT / "data" / "recordings"
VECTORS = ROOT / "shared" / "test-vectors" / "chain_vectors.json"
DEVICE = "pg-test-001"


def make_test_signer():
    """TEST ONLY key from the public seed in the vectors file."""
    vectors = json.loads(VECTORS.read_text(encoding="utf-8"))
    return Signer.from_seed(hashlib.sha256(vectors["test_only_seed_text"].encode()).digest())


def make_record(seq, **changes):
    values = dict(
        device_id=DEVICE, seq=seq, t_s=600.0 * seq, source="sim", temp_c=5.0 + seq / 100,
        rh_pct=45.0, shock_g=0.0, ambient_c=21.0, cooling_duty=0.5, potency=1.0,
        shelf_life_used_fraction=0.0, tau_eq_h=0.0, verdict="ok", trust_level="trusted",
        bound_tau_eq_h=None, bound_low_tau_eq_h=None,
    )  # fmt: skip
    values.update(changes)
    return build_record(**values)


def build_ledger(tmp_path, n=12, signer=None, device=DEVICE):
    signer = signer or make_test_signer()
    ledger = Ledger.create(new_run_id("test"), tmp_path)
    writer = ChainWriter(device, signer, ledger)
    for seq in range(n):
        writer.append(make_record(seq, device_id=device))
    writer.anchor()
    return ledger, signer


# ----------------------------------------------------------------- canonical record


@pytest.mark.parametrize(
    "value,unit,expected",
    [
        (0.00005, UNIT_E4, 1), (-0.00005, UNIT_E4, -1), (0.00004, UNIT_E4, 0),
        (5.00005, UNIT_E4, 50001), (-5.00005, UNIT_E4, -50001), (0.1 + 0.2, UNIT_E4, 3000),
        (4.2265, UNIT_E4, 42265), (2.5e-9, UNIT_E9, 3), (0.0005, UNIT_MS, 1), (600.0, UNIT_MS, 600000),
        (1.2345675, UNIT_E6, 1234568), (-0.0, UNIT_E4, 0), (0, UNIT_E4, 0), (None, UNIT_E4, None),
    ],
)  # fmt: skip
def test_rounding_is_half_away_from_zero_on_the_shortest_decimal(value, unit, expected):
    assert to_scaled_int(value, unit) == expected


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), True, "5", [1]])
def test_scaling_rejects_non_numbers(bad):
    with pytest.raises(ValueError):
        to_scaled_int(bad, UNIT_E4)


def test_scaling_rejects_integers_beyond_two_to_the_53():
    with pytest.raises(ValueError):
        to_scaled_int(1e13, UNIT_E4)


def test_canonical_bytes_are_deterministic_sorted_compact_and_float_free():
    a = make_record(3)
    reordered = dict(reversed(list(a.items())))
    assert canonical_bytes(a) == canonical_bytes(reordered)
    data = canonical_bytes(a)
    assert b" " not in data and b"\n" not in data
    text = data.decode("utf-8")
    assert text == json.dumps(a, sort_keys=True, separators=(",", ":"))
    assert list(json.loads(text)) == sorted(FIELDS)
    assert "." not in text.replace(DEVICE, "").replace("pg-record/1", "")  # no decimals anywhere
    assert parse_canonical(data) == a


def test_parse_canonical_rejects_everything_that_is_not_exactly_canonical():
    good = canonical_bytes(make_record(0))
    text = good.decode()
    for bad in (
        b"",
        b"not json",
        b"[]",
        b"\xff\xfe",
        good + b" ",
        text.replace(":", ": ", 1).encode(),
        text.replace('"seq":0', '"seq":0.0').encode(),
        text.replace('"seq":0', '"seq":1e0').encode(),
        text.replace('"seq":0', '"seq":NaN').encode(),
        text.replace('"verdict":"ok"', '"verdict":""').encode(),
        text[:-1].encode() + b',"extra":1}',
        text.replace('"seq":0', '"seq":true').encode(),
    ):
        with pytest.raises(ValueError):
            parse_canonical(bad)


def test_the_record_has_the_stated_fields_and_units():
    record = make_record(
        2, temp_c=-0.5, ambient_c=None, cooling_duty=None, potency=0.999999912,
        tau_eq_h=0.077005, bound_tau_eq_h=4400.5, bound_low_tau_eq_h=4381.25,
    )  # fmt: skip
    assert (
        record["temp"] == -5000 and record["ambient_c"] is None and record["cooling_duty"] is None
    )
    assert record["t_ms"] == 1_200_000 and record["potency"] == 999_999_912
    assert record["tau_eq_h"] == 77_005 and record["bound_tau_eq_h"] == 4_400_500_000
    assert record["bound_low_tau_eq_h"] == 4_381_250_000
    assert record["schema"] == "pg-record/1" and set(record) == set(FIELDS)


# ----------------------------------------------------------------- shared vectors


def test_the_shared_vectors_are_test_only_and_reproduce(tmp_path):
    vectors = json.loads(VECTORS.read_text(encoding="utf-8"))
    assert "TEST ONLY" in vectors["WARNING"]
    signer = make_test_signer()
    assert signer.public_key_bytes.hex() == vectors["public_key_hex"]
    previous = genesis_hash(vectors["device_id"])
    assert previous.hex() == vectors["genesis_hash_hex"]
    for item in vectors["records"]:
        record = build_record(
            device_id=vectors["device_id"], seq=item["record"]["seq"], **item["inputs"]
        )
        assert record == item["record"]
        canonical = canonical_bytes(record)
        assert canonical.hex() == item["canonical_hex"]
        assert signer.sign(canonical).hex() == item["signature_hex"]
        assert verify_signature(
            signer.public_key_bytes, bytes.fromhex(item["signature_hex"]), canonical
        )
        previous = link_hash(previous, canonical, bytes.fromhex(item["signature_hex"]))
        assert previous.hex() == item["hash_hex"]
    assert vectors["anchor"]["head_hex"] == previous.hex()
    for case in vectors["rounding_cases"]:
        assert to_scaled_int(case["value"], case["unit"]) == case["expected"]


def test_the_vectors_file_matches_its_generator():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "make_chain_vectors.py"), "--check"],
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    assert result.returncode == 0, result.stdout


def test_the_golden_recordings_and_existing_vectors_are_byte_identical_to_before_phase_4():
    expected = json.loads((ROOT / "shared" / "golden_sha256.json").read_text("utf-8"))["sha256"]
    assert len(expected) == 11
    for relative, digest in expected.items():
        assert hashlib.sha256((ROOT / relative).read_bytes()).hexdigest().upper() == digest, (
            relative
        )


# ----------------------------------------------------------------- signing


def test_sign_and_verify_round_trip_and_wrong_inputs():
    signer = make_test_signer()
    other = Signer.from_seed(hashlib.sha256(b"another TEST ONLY seed").digest())
    message = b"hello"
    signature = signer.sign(message)
    assert verify_signature(signer.public_key_bytes, signature, message)
    assert not verify_signature(signer.public_key_bytes, signature, b"hellO")
    assert not verify_signature(other.public_key_bytes, signature, message)
    for junk in (b"", b"x" * 63, b"x" * 64, None, "text", 5):
        assert verify_signature(signer.public_key_bytes, junk, message) is False
    for junk_key in (b"", b"x" * 31, b"\x00" * 32, None):
        assert verify_signature(junk_key, signature, message) is False
    assert signer.key_id in repr(signer) and "Signer(" in repr(signer)
    with pytest.raises(ValueError):
        Signer.from_seed(b"short")


# ----------------------------------------------------------------- the chain and every tamper action


def entries_of(tmp_path, n=12):
    ledger, signer = build_ledger(tmp_path, n)
    entries, anchor = ledger.read_entries(), ledger.latest_anchor()
    ledger.close()
    return entries, anchor, signer


def test_an_untouched_chain_verifies_with_and_without_an_anchor(tmp_path):
    entries, anchor, signer = entries_of(tmp_path)
    assert verify_chain(entries, signer.public_key_bytes).ok
    result = verify_chain(entries, signer.public_key_bytes, anchor)
    assert result.ok and result.anchor_checked and result.entries_checked == 12
    assert verify_chain([], signer.public_key_bytes).ok


def test_genesis_and_link_formula(tmp_path):
    entries, _, _ = entries_of(tmp_path, 3)
    expected = hashlib.sha256(b"potencyguard/genesis/v1" + DEVICE.encode()).digest()
    assert genesis_hash(DEVICE) == expected
    first = entries[0]
    assert first.hash == hashlib.sha256(expected + first.record + first.signature).digest()
    second = entries[1]
    assert second.hash == hashlib.sha256(first.hash + second.record + second.signature).digest()


def replace(entries, index, **changes):
    entry = entries[index]
    values = dict(
        seq=entry.seq,
        record=entry.record,
        signature=entry.signature,
        hash=entry.hash,
        key_id=entry.key_id,
    )
    values.update(changes)
    return [*entries[:index], Entry(**values), *entries[index + 1 :]]


def test_editing_one_value_is_detected_at_that_entry(tmp_path):
    entries, anchor, signer = entries_of(tmp_path)
    record = parse_canonical(entries[5].record)
    record["temp"] += 10_000
    result = verify_chain(
        replace(entries, 5, record=canonical_bytes(record)), signer.public_key_bytes, anchor
    )
    assert (result.ok, result.index, result.reason) == (False, 5, "bad_signature")


def test_deleting_an_entry_is_detected_at_the_gap(tmp_path):
    entries, anchor, signer = entries_of(tmp_path)
    result = verify_chain(entries[:4] + entries[5:], signer.public_key_bytes, anchor)
    assert (result.ok, result.index, result.reason) == (False, 4, "bad_sequence")


def test_reordering_two_entries_is_detected(tmp_path):
    entries, anchor, signer = entries_of(tmp_path)
    swapped = list(entries)
    swapped[6], swapped[7] = swapped[7], swapped[6]
    result = verify_chain(swapped, signer.public_key_bytes, anchor)
    assert (result.ok, result.index, result.reason) == (False, 6, "bad_sequence")


def test_a_replaced_signature_is_detected(tmp_path):
    entries, anchor, signer = entries_of(tmp_path)
    result = verify_chain(
        replace(entries, 3, signature=bytes(range(64))), signer.public_key_bytes, anchor
    )
    assert (result.ok, result.index, result.reason) == (False, 3, "bad_signature")


def test_a_wrong_stored_hash_is_a_broken_link(tmp_path):
    entries, anchor, signer = entries_of(tmp_path)
    result = verify_chain(replace(entries, 8, hash=b"\x01" * 32), signer.public_key_bytes, anchor)
    assert (result.ok, result.index, result.reason) == (False, 8, "bad_hash_link")


def test_impersonation_with_a_different_key_is_detected_even_with_a_rebuilt_chain(tmp_path):
    entries, anchor, signer = entries_of(tmp_path)
    attacker = Signer.generate()
    forged, previous = [], genesis_hash(DEVICE)
    for entry in entries:
        signature = attacker.sign(entry.record)
        previous = link_hash(previous, entry.record, signature)
        forged.append(Entry(entry.seq, entry.record, signature, previous, attacker.key_id))
    result = verify_chain(forged, signer.public_key_bytes, anchor)
    assert (result.ok, result.index, result.reason) == (False, 0, "bad_signature")
    # even with the key id copied, the signature itself fails
    disguised = [Entry(e.seq, e.record, e.signature, e.hash, signer.key_id) for e in forged]
    assert verify_chain(disguised, signer.public_key_bytes, anchor).reason == "bad_signature"


def test_entries_of_another_device_are_detected(tmp_path):
    entries, _, signer = entries_of(tmp_path)
    other_record = make_record(4, device_id="pg-other-001")
    swapped = replace(
        entries,
        4,
        record=canonical_bytes(other_record),
        signature=signer.sign(canonical_bytes(other_record)),
    )
    assert verify_chain(swapped, signer.public_key_bytes).reason == "wrong_device"


def test_tail_truncation_passes_without_an_anchor_and_is_found_with_one(tmp_path):
    entries, anchor, signer = entries_of(tmp_path)
    shorter = entries[:7]
    without = verify_chain(shorter, signer.public_key_bytes)
    assert without.ok  # THE LIMIT: nothing shows that entries are missing
    assert "cannot be detected" in str(without)
    found = verify_chain(shorter, signer.public_key_bytes, anchor)
    assert (found.ok, found.reason) == (False, "truncated")
    assert verify_chain([], signer.public_key_bytes, anchor).reason == "truncated"


def test_a_tampered_or_foreign_anchor_is_reported(tmp_path):
    entries, anchor, signer = entries_of(tmp_path)
    forged = Anchor(anchor.seq, anchor.head, anchor.statement, bytes(64), anchor.key_id)
    assert verify_chain(entries, signer.public_key_bytes, forged).reason == "bad_anchor"
    other = Signer.generate()
    foreign = make_anchor(other, DEVICE, anchor.seq, anchor.head)
    assert verify_chain(entries, signer.public_key_bytes, foreign).reason == "bad_anchor"
    wrong_head = make_anchor(signer, DEVICE, 5, b"\x02" * 32)
    result = verify_chain(entries, signer.public_key_bytes, wrong_head)
    assert (result.ok, result.index, result.reason) == (False, 5, "anchor_mismatch")
    wrong_device = make_anchor(signer, "pg-other-001", anchor.seq, anchor.head)
    assert verify_chain(entries, signer.public_key_bytes, wrong_device).reason == "bad_anchor"


def test_anything_malformed_is_reported_and_never_raises(tmp_path):
    entries, anchor, signer = entries_of(tmp_path, 4)
    key = signer.public_key_bytes
    garbage_lists = [
        [None], ["text"], [123], [object()], [{}], [(1, 2, 3)],
        [Entry(0, b"", b"", b"", "")], [Entry(0, b"{}", b"x", b"y", "k")],
        [Entry("0", entries[0].record, entries[0].signature, entries[0].hash, "k")],  # type: ignore[arg-type]
        [Entry(0, "str", b"", b"", "")],  # type: ignore[arg-type]
        [Entry(0, entries[0].record, None, entries[0].hash, "k")],  # type: ignore[arg-type]
        [Entry(0, b"\xff" * 10, b"", b"", "")],
    ]  # fmt: skip
    for entries_in in garbage_lists:
        result = verify_chain(entries_in, key, anchor)
        assert result.ok is False and result.reason in {
            "malformed",
            "bad_sequence",
            "bad_signature",
        }
    for bad_key in (b"", None, "text", b"x" * 40):
        assert verify_chain(entries, bad_key).ok is False
    for bad_anchor in ("text", 7, Anchor(0, b"", b"", b"", ""), Anchor(99, b"x", b"{}", b"s", "k")):
        assert verify_chain(entries, key, bad_anchor).ok is False
    assert verify_chain(None, key).ok is False  # type: ignore[arg-type]
    assert verify_chain(entries, key, device_id="pg-wrong-001").reason == "wrong_device"


def test_the_writer_checks_seq_and_device_and_resumes_a_ledger(tmp_path):
    ledger, signer = build_ledger(tmp_path, 3)
    writer = ChainWriter(DEVICE, signer, ledger)  # resumes after entry 2
    assert writer.next_seq == 3
    with pytest.raises(ValueError):
        writer.append(make_record(5))
    with pytest.raises(ValueError):
        writer.append(make_record(3, device_id="pg-other-001"))
    writer.append(make_record(3))
    assert verify_chain(ledger.read_entries(), signer.public_key_bytes, device_id=DEVICE).ok
    empty = Ledger.create(new_run_id("empty"), tmp_path)
    with pytest.raises(ValueError):
        ChainWriter(DEVICE, signer, empty).anchor()
    ledger.close(), empty.close()


# ----------------------------------------------------------------- the ledger


def test_the_ledger_is_append_only_and_named_by_run_id(tmp_path):
    ledger, _ = build_ledger(tmp_path, 5)
    assert ledger.path.parent == tmp_path and ledger.path.suffix == ".sqlite"
    public_names = [n for n in dir(Ledger) if not n.startswith("_")]
    assert not [
        n
        for n in public_names
        if n.split("_")[0]
        in {"update", "delete", "remove", "set", "replace", "clear", "truncate", "drop"}
    ]
    db = sqlite3.connect(ledger.path)
    for statement in (
        "UPDATE entries SET key_id='x' WHERE seq=1",
        "DELETE FROM entries WHERE seq=1",
        "UPDATE anchors SET seq=0",
        "DELETE FROM anchors",
    ):
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            db.execute(statement)
    db.close()
    assert [e.seq for e in ledger.read_entries()] == list(range(5))
    ledger.close()


def test_every_run_gets_a_new_file_and_ids_are_checked(tmp_path):
    a, b = new_run_id("x y/z"), new_run_id("x y/z")
    assert a != b and "/" not in a and " " not in a
    first = Ledger.create(a, tmp_path)
    first.close()
    with pytest.raises(FileExistsError):
        Ledger.create(a, tmp_path)
    for bad in ("", "../escape", "a/b", "a b", "x" * 100):
        with pytest.raises(ValueError):
            Ledger.create(bad, tmp_path)
    with pytest.raises(FileNotFoundError):
        Ledger.open(tmp_path / "missing.sqlite")


def test_entries_are_read_back_in_order_even_if_stored_out_of_order(tmp_path):
    ledger = Ledger.create(new_run_id("order"), tmp_path)
    signer = make_test_signer()
    entries = []
    previous = genesis_hash(DEVICE)
    for seq in (0, 1, 2):
        canonical = canonical_bytes(make_record(seq))
        signature = signer.sign(canonical)
        previous = link_hash(previous, canonical, signature)
        entries.append(Entry(seq, canonical, signature, previous, signer.key_id))
    for entry in (entries[2], entries[0], entries[1]):
        ledger.append(entry)
    assert [e.seq for e in ledger.read_entries()] == [0, 1, 2]
    assert ledger.last_entry().seq == 2 and ledger.latest_anchor() is None
    ledger.close()


# ----------------------------------------------------------------- keys never inside the repo


def test_the_default_key_directory_is_outside_the_repo():
    assert ROOT not in default_key_dir().resolve().parents


def test_a_key_is_created_once_stored_outside_and_reloaded(tmp_path):
    first = load_or_create_signer(tmp_path / "keys")
    again = load_or_create_signer(tmp_path / "keys")
    assert first.key_id == again.key_id and first.public_key_bytes == again.public_key_bytes
    assert (tmp_path / "keys" / "device_ed25519.key").exists()
    assert ROOT not in (tmp_path / "keys").resolve().parents
    assert "key_id" in repr(first) and first.public_key_bytes.hex() not in repr(first)


def test_no_key_file_or_pem_block_exists_anywhere_in_the_repo():
    marker = ("-----" + "BEGIN").encode()
    skip = {".git", "node_modules", "__pycache__", ".pytest_cache", ".ruff_cache", "runs"}
    found = []
    for path in ROOT.rglob("*"):
        if any(part in skip for part in path.relative_to(ROOT).parts) or not path.is_file():
            continue
        if path.suffix in {".key", ".pem", ".p8", ".pk8", ".priv"} or path.name.startswith(
            ("id_ed25519", "device_ed25519")
        ):
            found.append(f"key-like file: {path.relative_to(ROOT)}")
        elif path.stat().st_size < 3_000_000 and marker in path.read_bytes():
            found.append(f"PEM block in {path.relative_to(ROOT)}")
    assert not found, found


def test_gitignore_covers_keys_and_ledgers():
    lines = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    for pattern in (
        "*.pem",
        "*.key",
        "keys/",
        "data/runs/",
        "*.sqlite",
        "*.p8",
        "id_ed25519*",
        "device_ed25519*",
    ):
        assert pattern in lines, pattern


# ----------------------------------------------------------------- the runner equals the existing pipeline


@pytest.mark.parametrize(
    "name", ["baseline_ok", "hidden_spoilage", "spoof_attempt", "reefer_failure", "sensor_glitch"]
)
def test_the_signed_series_equals_what_the_twin_command_computes(name, product, box, tmp_path):
    path = RECORDINGS / f"{name}.jsonl"
    summary = run_recording(path, product, box, make_test_signer(), DEFAULT_DEVICE_ID, tmp_path)
    assert summary.chain.ok and summary.chain.anchor_checked
    analysis = analyse(path, product, box)
    with Ledger.open(summary.ledger_path) as ledger:
        entries = ledger.read_entries()
    assert len(entries) == len(analysis.states) == summary.entries
    for entry, reading, state, potency, assessment in zip(
        entries,
        analysis.readings,
        analysis.states,
        analysis.potency,
        analysis.assessments,
        strict=True,
    ):
        record = parse_canonical(entry.record)
        assert record["potency"] == to_scaled_int(potency.potency, UNIT_E9)
        assert record["shelf_life_used_fraction"] == to_scaled_int(
            potency.shelf_life_used_fraction, UNIT_E9
        )
        assert record["tau_eq_h"] == to_scaled_int(potency.tau_eq_h, UNIT_E6)
        assert record["verdict"] == state.verdict == assessment.verdict
        assert record["trust_level"] == assessment.trust_level
        assert record["temp"] == to_scaled_int(reading.temp_c, UNIT_E4)
        assert record["t_ms"] == to_scaled_int(reading.t_s, UNIT_MS)
        assert record["source"] == "sim"
        for field, value in (
            ("bound_tau_eq_h", assessment.bound_tau_eq_h),
            ("bound_low_tau_eq_h", assessment.bound_low_tau_eq_h),
        ):
            assert record[field] == to_scaled_int(value, UNIT_E6)
    assert summary.final_trust_level == analysis.assessments[-1].trust_level
    assert summary.last_potency == analysis.potency[-1].potency


def test_a_falsified_recording_is_signed_with_bounds_and_the_untrusted_level(
    product, box, tmp_path
):
    summary = run_recording(
        RECORDINGS / "hidden_spoilage.jsonl", product, box, make_test_signer(), runs_dir=tmp_path
    )
    with Ledger.open(summary.ledger_path) as ledger:
        last = parse_canonical(ledger.read_entries()[-1].record)
    assert last["trust_level"] == "untrusted"
    assert last["bound_tau_eq_h"] is not None and last["bound_low_tau_eq_h"] is not None
    assert last["bound_low_tau_eq_h"] <= last["bound_tau_eq_h"]


def test_the_runner_writes_the_public_key_next_to_the_ledger_not_the_private_one(
    product, box, tmp_path
):
    signer = make_test_signer()
    summary = run_recording(
        RECORDINGS / "baseline_ok.jsonl", product, box, signer, runs_dir=tmp_path
    )
    pub = summary.ledger_path.with_suffix(".pubkey")
    assert pub.read_text("utf-8").strip() == signer.public_key_bytes.hex()
    assert sorted(
        p.suffix for p in tmp_path.iterdir() if p.suffix not in {".sqlite-wal", ".sqlite-shm"}
    ) == [".pubkey", ".sqlite"]


def test_pi_source_is_a_clear_stub():
    source = PiSource()
    for call in (source.start, source.read):
        with pytest.raises(NotImplementedError, match="no Raspberry Pi hardware"):
            call()
    source.close()


def test_run_command_prints_a_short_summary_and_returns_zero(tmp_path):
    out = io.StringIO()
    code = edge_main(
        [
            "run",
            "--recording",
            str(RECORDINGS / "spoof_attempt.jsonl"),
            "--key-dir",
            str(tmp_path / "k"),
            "--ledger-dir",
            str(tmp_path / "l"),
        ],
        out,
    )
    text = out.getvalue()
    assert code == 0
    for needle in (
        "signed entries",
        "verdicts",
        "chain OK",
        "last potency",
        "final trust",
        "untrusted",
        "do not stop a false sensor input",
    ):
        assert needle in text
    assert "BEGIN" not in text and "PRIVATE" not in text
    out = io.StringIO()
    assert (
        edge_main(
            ["run", "--recording", str(tmp_path / "nope.jsonl"), "--key-dir", str(tmp_path / "k")],
            out,
        )
        == 2
    )


def test_run_all_covers_every_recording(tmp_path):
    out = io.StringIO()
    code = edge_main(
        ["run", "--all", "--key-dir", str(tmp_path / "k"), "--ledger-dir", str(tmp_path / "l")], out
    )
    assert code == 0 and out.getvalue().count("chain OK") == 9


def test_the_tamper_demo_shows_each_action_and_the_truncation_limit(tmp_path, product, box):
    summary = run_recording(
        RECORDINGS / "baseline_ok.jsonl", product, box, make_test_signer(), runs_dir=tmp_path
    )
    before = summary.ledger_path.read_bytes()
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "tamper_demo.py"), str(summary.ledger_path), "all", "--out-dir", str(tmp_path / "copies")],
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    text = result.stdout
    assert result.returncode == 0, result.stderr
    assert text.count("chain BROKEN") >= 6 and "bad_signature" in text and "bad_sequence" in text
    assert "without an anchor: chain OK" in text and "with the anchor:   chain BROKEN" in text
    assert "truncated" in text
    assert summary.ledger_path.read_bytes() == before  # the original is never changed
