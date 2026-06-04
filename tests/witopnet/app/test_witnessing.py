# -*- encoding: utf-8 -*-
"""
tests.app.test_witnessing module

"""

import errno
from types import SimpleNamespace
from unittest.mock import MagicMock

import falcon
from falcon import testing
from keri import kering

from witopnet.core import oobing, witnessing

CONTROLLER_AID = "ENsqL5zLYNbZf0kcOlx-ioqNWlatD9rKZZM4hbEI7nza"


def test_delete_witness_removes_registry_before_closing():
    witery = witnessing.Witnessery.__new__(witnessing.Witnessery)
    witery.wits = {}
    witery.db = SimpleNamespace(wits=MagicMock(), cids=MagicMock())
    witery.remove = MagicMock()

    witness = MagicMock()
    witness.aids = ["AID_1"]
    witness.hby = MagicMock()
    witery.wits["EID_1"] = witness

    witery.deleteWitness("EID_1")

    assert "EID_1" not in witery.wits
    witery.db.wits.rem.assert_called_once_with(keys=("EID_1",))
    witery.db.cids.rem.assert_called_once_with(keys=("AID_1",), val="EID_1")
    witery.remove.assert_called_once_with([witness])
    witness.hby.close.assert_called_once_with(clear=True)


def test_fd_exhaustion_detection_handles_oserror_and_lmdb_text():
    assert witnessing._isFdExhaustion(OSError(errno.EMFILE, "Too many open files"))
    assert witnessing._isFdExhaustion(RuntimeError("lmdb failure: Too many open files"))


def test_create_witness_fd_exhaustion_returns_service_unavailable():
    witery = MagicMock()
    witery.createWitness.side_effect = RuntimeError("lmdb failure: Too many open files")

    endpoint = witnessing.WitnessCollectionEnd(witery=witery)
    app = falcon.App()
    app.add_route("/witnesses", endpoint)
    client = testing.TestClient(app)

    response = client.simulate_post("/witnesses", json={"aid": CONTROLLER_AID})

    assert response.status == falcon.HTTP_503
    assert response.json["title"] == "Witness service unavailable"
    witery._logFdExhaustion.assert_called_once_with(CONTROLLER_AID)


def test_oobi_closed_witness_db_returns_not_found():
    aid = "EAID123"
    witness = SimpleNamespace(
        hby=SimpleNamespace(
            kevers={aid: SimpleNamespace(serder=MagicMock())},
            db=SimpleNamespace(opened=False),
            prefixes=set(),
            habs={},
        )
    )
    witery = MagicMock()
    witery.lookup.return_value = witness

    endpoint = oobing.OOBIEnd(witery=witery)
    app = falcon.App()
    app.add_route("/oobi/{aid}/{role}", endpoint)
    client = testing.TestClient(app)

    response = client.simulate_get(f"/oobi/{aid}/controller")

    assert response.status == falcon.HTTP_404


def test_oobi_defaults_to_v2_and_supports_explicit_v1_query_param():
    aid = "EAID123"
    calls = []

    class FakeHab:
        def replyToOobi(self, **kwa):
            # Capture the exact version kwargs so this test checks endpoint
            # policy directly instead of depending on serialized byte details
            calls.append(kwa)
            return bytearray(b"oobi")

        def replay(self, aid):
            return bytearray()

    witness = SimpleNamespace(
        hby=SimpleNamespace(
            kevers={
                aid: SimpleNamespace(
                    serder=object(),
                    prefixer=SimpleNamespace(qb64=aid),
                    wits=[],
                )
            },
            db=SimpleNamespace(opened=True, fullyWitnessed=lambda serder: True),
            prefixes={aid},
            habs={aid: FakeHab()},
        )
    )
    witery = MagicMock()
    witery.lookup.side_effect = lambda target: witness if target == aid else None
    witery.db = SimpleNamespace(cids=SimpleNamespace(get=lambda keys: None))

    endpoint = oobing.OOBIEnd(witery=witery)
    app = falcon.App()
    app.add_route("/oobi/{aid}/{role}", endpoint)
    client = testing.TestClient(app)

    response = client.simulate_get(f"/oobi/{aid}/controller")

    assert response.status_code == 200

    # Generated OOBIs are v2-first when the request does not pin a version
    assert calls[0]["version"] == kering.Vrsn_2_0
    assert calls[0]["pvrsn"] == kering.Vrsn_2_0

    response = client.simulate_get(
        f"/oobi/{aid}/controller",
        query_string="version=1.0",
    )

    assert response.status_code == 200

    # v1 Users can still force a v1 OOBI reply through the query string
    assert calls[1]["version"] == kering.Vrsn_1_0
    assert calls[1]["pvrsn"] == kering.Vrsn_1_0


def test_delete_missing_witness_returns_not_found():
    witery = MagicMock()
    witery.deleteWitness.side_effect = ValueError("missing witness")

    endpoint = witnessing.WitnessResourceEnd(witery=witery)
    app = falcon.App()
    app.add_route("/witnesses/{eid}", endpoint)
    client = testing.TestClient(app)

    response = client.simulate_delete(
        "/witnesses/BHMXjwXav5p1j1tvD6cgIPoLE7ke3us0YUmTMPKLjmgi"
    )

    assert response.status == falcon.HTTP_404
