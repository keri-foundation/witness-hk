# -*- encoding: utf-8 -*-
"""
tests.app.test_witnessing module

"""

import errno
import json
import re
from types import SimpleNamespace
from unittest.mock import MagicMock

import falcon
from falcon import testing
from hio.base import doing
from keri import kering
from keri.app import habbing
from keri.help import helping

from witopnet.core import basing, oobing, witnessing

CONTROLLER_AID = "ENsqL5zLYNbZf0kcOlx-ioqNWlatD9rKZZM4hbEI7nza"
STREAM_MESSAGE_PATTERN = re.compile(rb'\{"v":"([^"]+)","t":"([^"]+)"')


def _stream_messages(stream):
    """Return `(version, ilk)` pairs for each JSON KERI message in a CESR stream.

    OOBI responses concatenate JSON KERI bodies with CESR attachments, so this
    helper inspects each serialized body directly instead of assuming the first
    message tells the whole versioning story for the stream.
    """
    messages = []
    for version, ilk in STREAM_MESSAGE_PATTERN.findall(stream):
        messages.append(
            (kering.deversify(version.decode("utf-8")).pvrsn, ilk.decode("utf-8"))
        )

    return messages


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


def test_self_owned_oobi_replays_v2_kel_and_reuses_stored_reply_records():
    """Self-owned OOBIs should replay KEL history and reuse stored reply versions."""

    with habbing.openHab(
        name="wan-oobi",
        transferable=False,
        salt=b"0123456789fedoob",
        version=kering.Vrsn_2_0,
    ) as (_, wanHab):
        url = "http://127.0.0.1:5642/"
        msgs = bytearray()

        # Set up the witness and its OOBI endpoint
        msgs.extend(
            wanHab.makeEndRole(
                eid=wanHab.pre,
                role=kering.Roles.controller,
                stamp=helping.nowIso8601(),
                version=kering.Vrsn_2_0,
            )
        )
        msgs.extend(
            wanHab.makeLocScheme(
                url=url,
                scheme=kering.Schemes.http,
                stamp=helping.nowIso8601(),
                version=kering.Vrsn_2_0,
            )
        )

        # Parse the records
        wanHab.psr.parse(ims=msgs)

        # Set up the doist and witery
        doist = doing.Doist(limit=1.0, tock=0.03125, real=True)
        safe = basing.Baser(name=wanHab.name, temp=wanHab.temp)
        witery = witnessing.Witnessery(db=safe, temp=wanHab.temp)
        deeds = doist.enter(doers=[witery])
        doist.recur(deeds=deeds)

        endpoint = oobing.OOBIEnd(witery=witery)
        app = falcon.App()
        app.add_route("/witnesses", witnessing.WitnessCollectionEnd(witery))
        app.add_route("/oobi/{aid}", endpoint)
        app.add_route("/oobi/{aid}/{role}", endpoint)
        client = testing.TestClient(app)

        # Provision a witness identifier for wanHab
        rep_w = client.simulate_post(
            path="/witnesses", body=json.dumps({"aid": wanHab.pre})
        )
        assert rep_w.status == falcon.HTTP_OK
        witness_aid = rep_w.json["eid"]

        # Fetch the OOBI and assert it is successful and parse the messages
        response = client.simulate_get(f"/oobi/{witness_aid}")
        assert response.status_code == 200
        messages = _stream_messages(response.content)

        # Assert that the inception is v2
        assert messages[0][1] == "icp"
        assert messages[0][0] == kering.Vrsn_2_0

        # With the simpler `replyToOobi()` path, stored reply records come back
        # in whatever version they were originally authored. This witness's
        # endpoint metadata was created as v2, so the discovery replies remain
        # v2 alongside the replayed v2 KEL history.
        default_reply_versions = [version for version, ilk in messages if ilk == "rpy"]
        assert default_reply_versions
        assert all(version == kering.Vrsn_2_0 for version in default_reply_versions)

        # Fetch the OOBI again and confirm the stored reply versions remain
        # stable across repeated requests.
        response = client.simulate_get(f"/oobi/{witness_aid}")
        assert response.status_code == 200
        messages = _stream_messages(response.content)

        # The replayed KEL stays untouched, and the stored reply records keep
        # their original authored v2 format.
        assert messages[0][1] == "icp"
        assert messages[0][0] == kering.Vrsn_2_0

        v2_reply_versions = [version for version, ilk in messages if ilk == "rpy"]
        assert v2_reply_versions
        assert all(version == kering.Vrsn_2_0 for version in v2_reply_versions)


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
