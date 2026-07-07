"""Tests for JSONL I/O and file hashing utilities."""
from __future__ import annotations

import json
from pathlib import Path

from src.ood.common.io import md5_file, read_jsonl, write_jsonl


class TestJsonlRoundtrip:
    def test_write_then_read(self, tmp_dir: Path):
        records = [{"a": 1, "b": "hello"}, {"a": 2, "b": "world"}]
        p = tmp_dir / "out.jsonl"
        write_jsonl(p, records)
        loaded = read_jsonl(p)
        assert loaded == records

    def test_creates_parent_dirs(self, tmp_dir: Path):
        p = tmp_dir / "nested" / "deep" / "file.jsonl"
        write_jsonl(p, [{"x": 1}])
        assert p.exists()

    def test_empty_list(self, tmp_dir: Path):
        p = tmp_dir / "empty.jsonl"
        write_jsonl(p, [])
        assert read_jsonl(p) == []

    def test_unicode_preserved(self, tmp_dir: Path):
        records = [{"msg": "こんにちは"}]
        p = tmp_dir / "utf8.jsonl"
        write_jsonl(p, records)
        loaded = read_jsonl(p)
        assert loaded[0]["msg"] == "こんにちは"

    def test_skip_blank_lines(self, tmp_dir: Path):
        p = tmp_dir / "blank.jsonl"
        p.write_text('{"a":1}\n\n{"b":2}\n', encoding="utf-8")
        loaded = read_jsonl(p)
        assert len(loaded) == 2

    def test_one_line_per_record(self, tmp_dir: Path):
        records = [{"n": i} for i in range(5)]
        p = tmp_dir / "multi.jsonl"
        write_jsonl(p, records)
        lines = [l for l in p.read_text().splitlines() if l.strip()]
        assert len(lines) == 5
        for line in lines:
            json.loads(line)  # must be valid JSON


class TestMd5File:
    def test_deterministic(self, tmp_dir: Path):
        p = tmp_dir / "f.bin"
        p.write_bytes(b"hello world")
        assert md5_file(p) == md5_file(p)

    def test_known_value(self, tmp_dir: Path):
        """Empty file has well-known MD5."""
        p = tmp_dir / "empty.bin"
        p.write_bytes(b"")
        assert md5_file(p) == "d41d8cd98f00b204e9800998ecf8427e"

    def test_different_content_different_hash(self, tmp_dir: Path):
        p1 = tmp_dir / "a.bin"
        p2 = tmp_dir / "b.bin"
        p1.write_bytes(b"aaa")
        p2.write_bytes(b"bbb")
        assert md5_file(p1) != md5_file(p2)

    def test_returns_hex_string(self, tmp_dir: Path):
        p = tmp_dir / "h.bin"
        p.write_bytes(b"data")
        h = md5_file(p)
        assert isinstance(h, str)
        assert len(h) == 32
        assert all(c in "0123456789abcdef" for c in h)
