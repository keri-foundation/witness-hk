# -*- encoding: utf-8 -*-
"""
tests.witopnet.app.test_indirecting module

Unit tests for KeyStateEnd and KeyLogEnd endpoint classes
"""

import falcon
from falcon import testing
from unittest.mock import MagicMock, patch
from keri.app.httping import CESR_DESTINATION_HEADER

from witopnet.app.indirecting import KeyStateEnd, KeyLogEnd


class TestKeyStateEnd:
    """Test suite for KeyStateEnd endpoint"""

    def setup_method(self):
        """Setup test fixtures for each test method"""
        # Create mock witery
        self.witery = MagicMock()

        # Create mock witness
        self.witness = MagicMock()
        self.witness_aid = "EBabiu0K7vLr6FRy8cZl_l5z7hMzOaV85ePSkVWRW9KI"

        # Create mock hab (habitat)
        self.witness.hab = MagicMock()
        self.witness.hab.pre = self.witness_aid

        # Create mock kever (key event receiver)
        self.test_pre = "ENsqL5zLYNbZf0kcOlx-ioqNWlatD9rKZZM4hbEI7nza"
        self.kever = MagicMock()
        self.kever.serder = MagicMock()
        self.kever.serder.saidb = b"test_said"
        self.kever.toader = MagicMock()
        self.kever.toader.num = 2

        # Mock kever state
        self.kever_state = MagicMock()
        self.kever_state._asdict = MagicMock(
            return_value={
                "i": self.test_pre,
                "s": "1",
                "d": "ETestSAID",
                "et": "ixn",
                "k": ["DTestKey"],
                "n": "ETestNext",
                "wits": ["EWit1", "EWit2"],
                "c": [],
                "ee": {"s": "0", "d": "EPrev"},
                "di": "",
            }
        )
        self.kever.state = MagicMock(return_value=self.kever_state)

        # Setup kevers dictionary
        self.witness.hab.kevers = {self.test_pre: self.kever}

        # Setup database mock
        self.witness.hab.db = MagicMock()

        # Create mock wigs (witness signatures)
        # Using valid CESR indexed signature format (0B prefix + 88 base64 chars)
        self.mock_wigs = [
            b"0BAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAg",
            b"0BAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAh",
        ]
        self.witness.hab.db.getWigs = MagicMock(return_value=self.mock_wigs)

        # Mock endorse method
        self.witness.hab.endorse = MagicMock(return_value=b"endorsed_data")

        # Setup witery lookup to return our witness
        self.witery.lookup = MagicMock(return_value=self.witness)

        # Create endpoint
        self.endpoint = KeyStateEnd(witery=self.witery)

        # Create Falcon app and test client
        self.app = falcon.App()
        self.app.add_route("/ksn", self.endpoint)
        self.client = testing.TestClient(self.app)

    def test_on_get_success(self):
        """Test successful key state query"""
        headers = {CESR_DESTINATION_HEADER: self.witness_aid}

        # Mock core.Siger to avoid needing valid CESR bytes
        with patch("witopnet.app.indirecting.core.Siger") as mock_siger:
            mock_siger_instance = MagicMock()
            mock_siger.return_value = mock_siger_instance

            response = self.client.simulate_get(
                "/ksn", query_string=f"pre={self.test_pre}", headers=headers
            )

            assert response.status == falcon.HTTP_200
            assert response.headers["Content-Type"] == "application/cesr"
            assert response.content == b"endorsed_data"

            # Verify witery.lookup was called with correct AID
            self.witery.lookup.assert_called_once_with(self.witness_aid)

            # Verify kever.state was called
            self.kever.state.assert_called_once()

            # Verify endorse was called
            self.witness.hab.endorse.assert_called_once()

    def test_on_get_missing_destination_header(self):
        """Test request without CESR destination header"""
        response = self.client.simulate_get("/ksn", query_string=f"pre={self.test_pre}")

        assert response.status == falcon.HTTP_400
        assert response.json["title"] == "CESR request destination header missing"

    def test_on_get_unknown_aid(self):
        """Test request with unknown AID"""
        unknown_aid = "EUnknownAID123"
        self.witery.lookup = MagicMock(return_value=None)

        headers = {CESR_DESTINATION_HEADER: unknown_aid}
        response = self.client.simulate_get(
            "/ksn", query_string=f"pre={self.test_pre}", headers=headers
        )

        assert response.status == falcon.HTTP_400
        assert "not recognized" in response.json["description"]

    def test_on_get_pre_not_found(self):
        """Test query for non-existent prefix"""
        unknown_pre = "EUnknownPrefix"
        self.witness.hab.kevers = {}  # Empty kevers

        headers = {CESR_DESTINATION_HEADER: self.witness_aid}
        response = self.client.simulate_get(
            "/ksn", query_string=f"pre={unknown_pre}", headers=headers
        )

        assert response.status == falcon.HTTP_404
        assert response.json["title"] == "AID not found"
        assert "not found" in response.json["description"]

    def test_on_get_insufficient_witness_receipts(self):
        """Test when witness receipts are insufficient"""
        # Mock getWigs to return fewer signatures than required
        self.witness.hab.db.getWigs = MagicMock(
            return_value=[b"sig1"]
        )  # Only 1, need 2

        headers = {CESR_DESTINATION_HEADER: self.witness_aid}

        # Mock core.Siger to avoid CESR parsing issues
        with patch("witopnet.app.indirecting.core.Siger") as mock_siger:
            mock_siger.return_value = MagicMock()

            response = self.client.simulate_get(
                "/ksn", query_string=f"pre={self.test_pre}", headers=headers
            )

            assert response.status == falcon.HTTP_404
            assert "Witness receipts not found" in response.json["title"]

    def test_on_get_no_witness_receipts(self):
        """Test when there are no witness receipts at all"""
        self.witness.hab.db.getWigs = MagicMock(return_value=[])

        headers = {CESR_DESTINATION_HEADER: self.witness_aid}
        response = self.client.simulate_get(
            "/ksn", query_string=f"pre={self.test_pre}", headers=headers
        )

        assert response.status == falcon.HTTP_404
        assert "Witness receipts not found" in response.json["title"]


class TestKeyLogEnd:
    """Test suite for KeyLogEnd endpoint"""

    def setup_method(self):
        """Setup test fixtures for each test method"""
        # Create mock witery
        self.witery = MagicMock()

        # Create mock witness
        self.witness = MagicMock()
        self.witness_aid = "EBabiu0K7vLr6FRy8cZl_l5z7hMzOaV85ePSkVWRW9KI"

        # Create mock hab (habitat)
        self.witness.hab = MagicMock()
        self.witness.hab.pre = self.witness_aid

        # Create mock kever
        self.test_pre = "ENsqL5zLYNbZf0kcOlx-ioqNWlatD9rKZZM4hbEI7nza"
        self.kever = MagicMock()
        self.kever.delpre = None  # No delegator
        self.kever.serder = MagicMock()
        self.kever.sner = MagicMock()
        self.kever.sner.num = 5  # Current sequence number

        # Setup kevers dictionary
        self.witness.hab.kevers = {self.test_pre: self.kever}

        # Setup database mock
        self.witness.hab.db = MagicMock()

        # Mock clonePreIter to return key event log messages
        self.mock_msgs = [b"msg1", b"msg2", b"msg3"]
        self.witness.hab.db.clonePreIter = MagicMock(return_value=iter(self.mock_msgs))

        # Mock fullyWitnessed
        self.witness.hab.db.fullyWitnessed = MagicMock(return_value=True)

        # Mock fetchAllSealingEventByEventSeal for anchor tests
        self.witness.hab.db.fetchAllSealingEventByEventSeal = MagicMock(
            return_value=[b"seal"]
        )

        # Setup witery lookup
        self.witery.lookup = MagicMock(return_value=self.witness)

        # Create endpoint
        self.endpoint = KeyLogEnd(witery=self.witery)

        # Create Falcon app and test client
        self.app = falcon.App()
        self.app.add_route("/log", self.endpoint)
        self.client = testing.TestClient(self.app)

    def test_on_get_success_basic(self):
        """Test successful key log query with basic parameters"""
        headers = {CESR_DESTINATION_HEADER: self.witness_aid}

        response = self.client.simulate_get(
            "/log", query_string=f"pre={self.test_pre}", headers=headers
        )

        assert response.status == falcon.HTTP_200
        assert response.headers["Content-Type"] == "application/cesr"

        # Verify the response contains the concatenated messages
        expected_data = b"".join(self.mock_msgs)
        assert response.content == expected_data

        # Verify witery.lookup was called
        self.witery.lookup.assert_called_once_with(self.witness_aid)

        # Verify clonePreIter was called with default fn=0
        self.witness.hab.db.clonePreIter.assert_called_with(pre=self.test_pre, fn=0)

    def test_on_get_with_fn_parameter(self):
        """Test key log query with fn (first seen number) parameter"""
        headers = {CESR_DESTINATION_HEADER: self.witness_aid}
        fn_hex = "a"  # 10 in decimal

        response = self.client.simulate_get(
            "/log", query_string=f"pre={self.test_pre}&fn={fn_hex}", headers=headers
        )

        assert response.status == falcon.HTTP_200

        # Verify clonePreIter was called with correct fn value
        self.witness.hab.db.clonePreIter.assert_called_with(pre=self.test_pre, fn=10)

    def test_on_get_with_sequence_number(self):
        """Test key log query with sequence number parameter"""
        headers = {CESR_DESTINATION_HEADER: self.witness_aid}
        sn_hex = "3"  # 3 in decimal

        response = self.client.simulate_get(
            "/log", query_string=f"pre={self.test_pre}&s={sn_hex}", headers=headers
        )

        assert response.status == falcon.HTTP_200

        # Verify fullyWitnessed was called
        self.witness.hab.db.fullyWitnessed.assert_called_once()

    def test_on_get_with_anchor(self):
        """Test key log query with anchor parameter"""
        headers = {CESR_DESTINATION_HEADER: self.witness_aid}
        anchor = "EAnchorSAID"

        response = self.client.simulate_get(
            "/log", query_string=f"pre={self.test_pre}&a={anchor}", headers=headers
        )

        assert response.status == falcon.HTTP_200

        # Verify fetchAllSealingEventByEventSeal was called
        self.witness.hab.db.fetchAllSealingEventByEventSeal.assert_called_once_with(
            pre=self.test_pre, seal=anchor
        )

    def test_on_get_with_delegator(self):
        """Test key log query when AID has a delegator"""
        # Setup delegator
        del_pre = "EDelegatorPrefix"
        self.kever.delpre = del_pre

        # Mock delegator messages
        del_msgs = [b"del_msg1", b"del_msg2"]

        # Configure clonePreIter to return different iterators for different calls
        def clone_pre_iter_side_effect(pre, fn):
            if pre == self.test_pre:
                return iter(self.mock_msgs)
            elif pre == del_pre:
                return iter(del_msgs)
            return iter([])

        self.witness.hab.db.clonePreIter = MagicMock(
            side_effect=clone_pre_iter_side_effect
        )

        headers = {CESR_DESTINATION_HEADER: self.witness_aid}
        response = self.client.simulate_get(
            "/log", query_string=f"pre={self.test_pre}", headers=headers
        )

        assert response.status == falcon.HTTP_200

        # Verify both regular and delegator messages are included
        expected_data = b"".join(self.mock_msgs) + b"".join(del_msgs)
        assert response.content == expected_data

    def test_on_get_missing_destination_header(self):
        """Test request without CESR destination header"""
        response = self.client.simulate_get("/log", query_string=f"pre={self.test_pre}")

        assert response.status == falcon.HTTP_400
        assert response.json["title"] == "CESR request destination header missing"

    def test_on_get_unknown_aid(self):
        """Test request with unknown AID"""
        unknown_aid = "EUnknownAID456"
        self.witery.lookup = MagicMock(return_value=None)

        headers = {CESR_DESTINATION_HEADER: unknown_aid}
        response = self.client.simulate_get(
            "/log", query_string=f"pre={self.test_pre}", headers=headers
        )

        assert response.status == falcon.HTTP_400
        assert "not recognized" in response.json["description"]

    def test_on_get_pre_not_found(self):
        """Test query for non-existent prefix"""
        unknown_pre = "EUnknownPrefix789"
        self.witness.hab.kevers = {}  # Empty kevers

        headers = {CESR_DESTINATION_HEADER: self.witness_aid}
        response = self.client.simulate_get(
            "/log", query_string=f"pre={unknown_pre}", headers=headers
        )

        assert response.status == falcon.HTTP_404
        assert response.json["title"] == "AID not found"
        assert "not found" in response.json["description"]

    def test_on_get_anchor_not_found(self):
        """Test query with anchor that doesn't exist"""
        # Mock fetchAllSealingEventByEventSeal to return empty list
        self.witness.hab.db.fetchAllSealingEventByEventSeal = MagicMock(return_value=[])

        headers = {CESR_DESTINATION_HEADER: self.witness_aid}
        anchor = "EMissingAnchor"

        response = self.client.simulate_get(
            "/log", query_string=f"pre={self.test_pre}&a={anchor}", headers=headers
        )

        assert response.status == falcon.HTTP_404
        assert "not found" in response.json["description"]

    def test_on_get_sequence_number_too_high(self):
        """Test query with sequence number higher than current"""
        # Set current sn to 5, but query for sn=10
        self.kever.sner.num = 5

        headers = {CESR_DESTINATION_HEADER: self.witness_aid}
        sn_hex = "a"  # 10 in decimal

        response = self.client.simulate_get(
            "/log", query_string=f"pre={self.test_pre}&s={sn_hex}", headers=headers
        )

        assert response.status == falcon.HTTP_404
        assert "not found" in response.json["description"]

    def test_on_get_not_fully_witnessed(self):
        """Test query when event is not fully witnessed"""
        self.witness.hab.db.fullyWitnessed = MagicMock(return_value=False)

        headers = {CESR_DESTINATION_HEADER: self.witness_aid}
        sn_hex = "2"

        response = self.client.simulate_get(
            "/log", query_string=f"pre={self.test_pre}&s={sn_hex}", headers=headers
        )

        assert response.status == falcon.HTTP_404
        assert "not found" in response.json["description"]

    def test_on_get_no_events_found(self):
        """Test query when no events are found"""
        # Mock clonePreIter to return empty iterator
        self.witness.hab.db.clonePreIter = MagicMock(return_value=iter([]))

        headers = {CESR_DESTINATION_HEADER: self.witness_aid}
        response = self.client.simulate_get(
            "/log", query_string=f"pre={self.test_pre}", headers=headers
        )

        assert response.status == falcon.HTTP_404
        assert "No events found" in response.json["description"]

    def test_on_get_hex_parsing(self):
        """Test that hex parameters are correctly parsed"""
        headers = {CESR_DESTINATION_HEADER: self.witness_aid}

        # Test with hexadecimal values that won't trigger 404
        # Use sn within range (current is 5)
        sn_hex = "2"  # 2 in decimal
        fn_hex = "10"  # 16 in decimal

        response = self.client.simulate_get(
            "/log",
            query_string=f"pre={self.test_pre}&s={sn_hex}&fn={fn_hex}",
            headers=headers,
        )

        assert response.status == falcon.HTTP_200
        # Verify clonePreIter was called with correct decimal fn value
        self.witness.hab.db.clonePreIter.assert_called_with(pre=self.test_pre, fn=16)
