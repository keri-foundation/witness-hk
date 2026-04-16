# -*- encoding: utf-8 -*-
"""
tests.app.test_witnessing module

"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import falcon
from falcon import testing

from witopnet.core import oobing, witnessing


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


def test_oobi_closed_witness_db_returns_not_found():
    aid = "EAID123"
    witness = SimpleNamespace(
        hby=SimpleNamespace(
            kevers={aid: SimpleNamespace(serder=MagicMock())},
            db=None,
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
