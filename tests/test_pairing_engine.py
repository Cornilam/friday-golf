"""Tests for the pairing engine — covers all remainder cases."""

import sys
from pathlib import Path
from unittest.mock import patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from db import Member
from pairing_engine import _split_into_groups, generate_pairings


def _make_members(n: int) -> list[Member]:
    """Create n fake Member objects for testing."""
    return [
        Member(id=i, name=f"Player{i}", email=f"p{i}@test.com", active=True, created_at="")
        for i in range(1, n + 1)
    ]


class TestSplitIntoGroups:
    """Test the core group splitting logic."""

    def test_empty(self):
        assert _split_into_groups([]) == []

    def test_one_player(self):
        players = _make_members(1)
        groups = _split_into_groups(players)
        assert len(groups) == 1
        assert len(groups[0]) == 1

    def test_two_players(self):
        players = _make_members(2)
        groups = _split_into_groups(players)
        assert len(groups) == 1
        assert len(groups[0]) == 2

    def test_three_players(self):
        players = _make_members(3)
        groups = _split_into_groups(players)
        assert len(groups) == 1
        assert len(groups[0]) == 3

    def test_four_players_perfect_group(self):
        players = _make_members(4)
        groups = _split_into_groups(players)
        assert len(groups) == 1
        assert len(groups[0]) == 4

    def test_five_players_remainder_1(self):
        """5 players: should be groups of 3 + 2 (no solo player)."""
        players = _make_members(5)
        groups = _split_into_groups(players)
        sizes = sorted([len(g) for g in groups])
        assert sizes == [2, 3]
        assert sum(sizes) == 5

    def test_eight_players_perfect(self):
        players = _make_members(8)
        groups = _split_into_groups(players)
        assert len(groups) == 2
        assert all(len(g) == 4 for g in groups)

    def test_nine_players_remainder_1(self):
        """9 players: should avoid a solo. Expect groups like [4, 3, 2]."""
        players = _make_members(9)
        groups = _split_into_groups(players)
        sizes = sorted([len(g) for g in groups])
        assert sum(sizes) == 9
        assert 1 not in sizes  # no solo player

    def test_ten_players_remainder_2(self):
        """10 players: two groups of 4 + one twosome."""
        players = _make_members(10)
        groups = _split_into_groups(players)
        sizes = sorted([len(g) for g in groups])
        assert sizes == [2, 4, 4]
        assert sum(sizes) == 10

    def test_eleven_players_remainder_3(self):
        """11 players: two groups of 4 + one threesome."""
        players = _make_members(11)
        groups = _split_into_groups(players)
        sizes = sorted([len(g) for g in groups])
        assert sizes == [3, 4, 4]
        assert sum(sizes) == 11

    def test_twelve_players_perfect(self):
        players = _make_members(12)
        groups = _split_into_groups(players)
        assert len(groups) == 3
        assert all(len(g) == 4 for g in groups)

    def test_thirteen_players_remainder_1(self):
        """13 players: avoid a solo."""
        players = _make_members(13)
        groups = _split_into_groups(players)
        sizes = sorted([len(g) for g in groups])
        assert sum(sizes) == 13
        assert 1 not in sizes

    def test_sixteen_players_perfect(self):
        players = _make_members(16)
        groups = _split_into_groups(players)
        assert len(groups) == 4
        assert all(len(g) == 4 for g in groups)

    def test_all_players_accounted_for(self):
        """Every player appears in exactly one group."""
        for n in range(1, 25):
            players = _make_members(n)
            groups = _split_into_groups(players)
            all_in_groups = [p for g in groups for p in g]
            assert len(all_in_groups) == n, f"Failed for n={n}"
            assert set(p.id for p in all_in_groups) == set(
                p.id for p in players
            ), f"Missing/duplicate players for n={n}"

    def test_no_group_larger_than_4(self):
        """No group should exceed 4 players."""
        for n in range(1, 25):
            players = _make_members(n)
            groups = _split_into_groups(players)
            for g in groups:
                assert len(g) <= 4, f"Group of {len(g)} for n={n}"

    def test_no_solo_player_when_possible(self):
        """No solo player for n >= 2."""
        for n in range(2, 25):
            players = _make_members(n)
            groups = _split_into_groups(players)
            for g in groups:
                assert len(g) >= 2, f"Solo player for n={n}"


class TestGeneratePairings:
    """Test the full generate_pairings function."""

    def test_empty_players(self):
        assert generate_pairings([], []) == []

    def test_randomness(self):
        """Groups should be shuffled (not always in order)."""
        players = _make_members(8)
        # Run multiple times and check we get different orderings
        orderings = set()
        for _ in range(20):
            groups = generate_pairings(players, [])
            order = tuple(p.id for g in groups for p in g["players"])
            orderings.add(order)
        # With 8 players shuffled, we should get multiple orderings in 20 tries
        assert len(orderings) > 1

    def test_tee_time_assignment(self):
        """Tee times should be assigned to groups in order."""
        players = _make_members(8)
        tee_times = [
            type("TeeTime", (), {"id": 100})(),
            type("TeeTime", (), {"id": 200})(),
        ]
        groups = generate_pairings(players, tee_times)
        assert groups[0]["tee_time_id"] == 100
        assert groups[1]["tee_time_id"] == 200

    def test_more_groups_than_tee_times(self):
        """Extra groups should get tee_time_id=None."""
        players = _make_members(12)
        tee_times = [type("TeeTime", (), {"id": 100})()]
        groups = generate_pairings(players, tee_times)
        assert groups[0]["tee_time_id"] == 100
        for g in groups[1:]:
            assert g["tee_time_id"] is None


class TestParseReplyStatus:
    """Test email reply parsing.

    We import parse_reply_status with google libs mocked out since they're
    not needed for this pure-logic function.
    """

    @staticmethod
    def _get_parse_fn():
        import importlib
        from unittest.mock import MagicMock

        # Mock google libs so email_client can import without them installed
        import sys
        mods = [
            "google", "google.auth", "google.auth.transport",
            "google.auth.transport.requests", "google.oauth2",
            "google.oauth2.credentials", "google_auth_oauthlib",
            "google_auth_oauthlib.flow", "googleapiclient",
            "googleapiclient.discovery", "googleapiclient.errors",
        ]
        for m in mods:
            if m not in sys.modules:
                sys.modules[m] = MagicMock()

        import email_client
        importlib.reload(email_client)
        return email_client.parse_reply_status

    def test_in_keywords(self):
        parse = self._get_parse_fn()
        assert parse("I'm in!") == "in"
        assert parse("Yes") == "in"
        assert parse("count me in") == "in"
        assert parse("IN") == "in"
        assert parse("playing") == "in"

    def test_out_keywords(self):
        parse = self._get_parse_fn()
        assert parse("Out this week") == "out"
        assert parse("No") == "out"
        assert parse("Can't make it") == "out"
        assert parse("Skip") == "out"
        assert parse("not this week") == "out"

    def test_unclear(self):
        parse = self._get_parse_fn()
        assert parse("Maybe, let me check") is None
        assert parse("What time?") is None
        assert parse("") is None

    def test_ignores_quoted_text(self):
        parse = self._get_parse_fn()
        reply = "Out\n\n> On Monday, Bot wrote:\n> Reply IN or OUT"
        assert parse(reply) == "out"
