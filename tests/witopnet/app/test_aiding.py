# -*- encoding: utf-8 -*-
"""
tests.app.test_aiding module

"""

import json

import falcon

import pyotp
from falcon import testing
from hio.base import doing
from keri import kering
from keri.app import habbing
from keri.app.httping import (
    CESR_ATTACHMENT_HEADER,
    CESR_CONTENT_TYPE,
    CESR_DESTINATION_HEADER,
)
from keri.core import coring, serdering, counting
from keri.help import helping

from witopnet.app import aiding, indirecting
from witopnet.core import basing, witnessing


def _simulate_cesr_post(client, *, path, msg, destination, headers=None):
    """POST a signed CESR/KERI message using the production HTTP envelope.

    The witness endpoints receive the event body and its attachment stream
    separately, so tests should exercise the same split body/header format that
    real clients use on the wire.
    """
    serder = serdering.SerderKERI(raw=msg)
    attachments = msg[serder.size :]
    request_headers = {
        CESR_ATTACHMENT_HEADER: attachments.decode("utf-8"),
        "content-type": CESR_CONTENT_TYPE,
        CESR_DESTINATION_HEADER: destination,
    }
    if headers:
        request_headers.update(headers)

    return client.simulate_post(
        path=path,
        body=serder.raw.decode("utf-8"),
        headers=request_headers,
    )


def _create_cesr_request(*, path, msg, destination, headers=None):
    """Build a Falcon request object that mirrors a real CESR HTTP submission.

    This is used when we want to call the endpoint method directly rather than
    go through Falcon's full WSGI test client machinery.
    """
    serder = serdering.SerderKERI(raw=msg)
    attachments = msg[serder.size :]
    request_headers = {
        CESR_ATTACHMENT_HEADER: attachments.decode("utf-8"),
        "content-type": CESR_CONTENT_TYPE,
        CESR_DESTINATION_HEADER: destination,
    }
    if headers:
        request_headers.update(headers)

    return testing.create_req(
        path=path,
        method="POST",
        headers=request_headers,
        body=serder.raw.decode("utf-8"),
    )


def _seed_endpoint_records(hab, *, url, version=None):
    """Create the witness endpoint metadata that test services expect at boot.

    The witness runtime expects its local controller role and HTTP location
    records to already exist in the habitat database, so integration-style
    tests seed those records the same way the production bootstrap flow does.
    """
    recording = dict(stamp=helping.nowIso8601())
    if version is not None:
        recording["version"] = version

    msgs = bytearray()
    msgs.extend(
        hab.makeEndRole(
            eid=hab.pre,
            role=kering.Roles.controller,
            **recording,
        )
    )
    msgs.extend(
        hab.makeLocScheme(
            url=url,
            scheme=kering.Schemes.http,
            **recording,
        )
    )
    hab.psr.parse(ims=msgs)


def _start_witery(hab):
    """Start an in-memory Witnessery backed by the supplied habitat settings."""
    doist = doing.Doist(limit=1.0, tock=0.03125, real=True)
    safe = basing.Baser(name=hab.name, temp=hab.temp)
    witery = witnessing.Witnessery(db=safe, temp=hab.temp)
    deeds = doist.enter(doers=[witery])
    doist.recur(deeds=deeds)
    return doist, witery


def test_aids_uses_message_protocol_version(multipart):
    """Regression: KERI10 CESR attachments must parse with the event's pvrsn.

    Newer keripy defaults attachment decoding to CESR v2 unless ``version=`` is
    supplied; without matching v1, controller sigs are dropped and /aids returns
    ``KEL part not valid inception event``.
    """
    with (
        habbing.openHab(name="bob", salt=b"0123456789fedbob") as (_, bobHab),
        habbing.openHab(name="wan", transferable=False, salt=b"0123456789fedcba") as (
            _,
            wanHab,
        ),
    ):
        _seed_endpoint_records(
            wanHab,
            url="http://127.0.0.1:5642/",
            version=wanHab.kever.serder.pvrsn,
        )
        _doist, witery = _start_witery(wanHab)

        app = falcon.App()
        app.add_route("/witnesses", witnessing.WitnessCollectionEnd(witery))
        aiding.loadEnds(app=app, witery=witery)
        client = testing.TestClient(app)

        rep = client.simulate_post(
            path="/witnesses", body=json.dumps({"aid": bobHab.pre})
        )
        assert rep.status == falcon.HTTP_OK
        bob_wit = rep.json["eid"]
        witness = witery.wits[bob_wit]

        kel = bobHab.msgOwnEvent(sn=0)
        serder = serdering.SerderKERI(raw=kel)
        assert kering.deversify(serder.ked["v"]).pvrsn.major == 1

        body, headers = multipart.create(dict(kel=kel))
        headers[CESR_DESTINATION_HEADER] = bob_wit
        rep = client.simulate_post(path="/aids", body=body, headers=headers)
        assert rep.status == falcon.HTTP_200
        assert "totp" in rep.json and "oobi" in rep.json
        assert bobHab.pre in witness.hab.kevers


def test_http_post_uses_inbound_version_across_event_types():
    """Tests `POST /` should parse real v1 and v2 bodies using each message's v field"""

    cases = (
        ("bob-http-v1", b"0123456789fehtv1", kering.Vrsn_1_0),
        ("bob-http-v2", b"0123456789fehtv2", kering.Vrsn_2_0),
    )

    for bob_name, bob_salt, version in cases:
        with (
            habbing.openHab(name=bob_name, salt=bob_salt, version=version) as (
                _,
                bobHab,
            ),
            habbing.openHab(
                name=f"wan-{bob_name}",
                transferable=False,
                salt=b"0123456789fehtwa",
                version=kering.Vrsn_2_0,
            ) as (_, wanHab),
        ):
            _seed_endpoint_records(
                wanHab,
                url="http://127.0.0.1:5642/",
                version=wanHab.kever.serder.pvrsn,
            )
            _doist, witery = _start_witery(wanHab)

            http_end = indirecting.HttpEnd(witery=witery)
            app = falcon.App()
            app.add_route("/witnesses", witnessing.WitnessCollectionEnd(witery))
            client = testing.TestClient(app)

            # Simulate the witness provisioning
            rep = client.simulate_post(
                path="/witnesses", body=json.dumps({"aid": bobHab.pre})
            )
            assert rep.status == falcon.HTTP_OK

            # Witness AID and object
            bob_wit = rep.json["eid"]
            witness = witery.wits[bob_wit]

            # Submit an inception event
            icp = bobHab.msgOwnEvent(sn=0)
            req = _create_cesr_request(
                path="/",
                msg=icp,
                destination=bob_wit,
            )
            rep = falcon.Response()
            http_end.on_post(req, rep)
            assert rep.status == falcon.HTTP_204

            # Assert that the witness stored Bob's event
            assert bobHab.pre in witness.hab.kevers

            # Assert that the stored event has the same version as the one sent
            stored_version = kering.deversify(
                witness.hab.kevers[bobHab.pre].serder.ked["v"]
            ).pvrsn
            assert stored_version == version

            # Submit a ksn query event to Bob's witness
            qry = bobHab.query(
                pre=bobHab.pre,
                src=bob_wit,
                route="ksn",
                version=version,
            )
            req = _create_cesr_request(
                path="/",
                msg=qry,
                destination=bob_wit,
            )

            # Assert handler accepted it without error
            rep = falcon.Response()
            http_end.on_post(req, rep)
            assert rep.status == falcon.HTTP_204

            # Submit a rpy message
            rpy = bobHab.makeEndRole(
                eid=bobHab.pre,
                role=kering.Roles.controller,
                version=version,
            )
            req = _create_cesr_request(
                path="/",
                msg=rpy,
                destination=bob_wit,
            )

            # Assert it was accepted without error
            # Use falcon for ease of testing
            rep = falcon.Response()
            http_end.on_post(req, rep)
            assert rep.status == falcon.HTTP_204


def test_encrypting_totp(multipart):
    with (
        habbing.openHab(name="bob", salt=b"0123456789fedbob") as (bobHby, bobHab),
        habbing.openHab(name="eve", salt=b"0123456789fedeve") as (eveHby, eveHab),
        habbing.openHab(name="wan", transferable=False, salt=b"0123456789fedcba") as (
            wanHby,
            wanHab,
        ),
    ):
        assert bobHab.pre == "ENsqL5zLYNbZf0kcOlx-ioqNWlatD9rKZZM4hbEI7nza"
        verfer = bobHab.kever.verfers[0]
        assert verfer.qb64 == "DIJUDTxA5U1aX0XkaX4_Sx6dBYEfZcIWynOmeXsDFeQP"

        assert wanHab.pre == "BGbLRtLXIslZvTfYz97dS9_EzQxp8kSTAMMtW-LmlXMI"
        url = "http://127.0.0.1:5642/"
        msgs = bytearray()
        msgs.extend(
            wanHab.makeEndRole(
                eid=wanHab.pre, role=kering.Roles.controller, stamp=helping.nowIso8601()
            )
        )

        msgs.extend(
            wanHab.makeLocScheme(
                url=url, scheme=kering.Schemes.http, stamp=helping.nowIso8601()
            )
        )
        wanHab.psr.parse(ims=msgs)

        tock = 0.03125
        limit = 1.0
        doist = doing.Doist(limit=limit, tock=tock, real=True)

        safe = basing.Baser(name=wanHab.name, temp=wanHab.temp)
        witery = witnessing.Witnessery(db=safe, temp=wanHab.temp)
        deeds = doist.enter(doers=[witery])
        doist.recur(deeds=deeds)

        app = falcon.App()
        witColEnd = witnessing.WitnessCollectionEnd(witery)
        app.add_route("/witnesses", witColEnd)

        aiding.loadEnds(app=app, witery=witery)
        receiptEnd = indirecting.ReceiptEnd(witery=witery, aids=[bobHab.pre])
        app.add_route("/receipts", receiptEnd)

        client = testing.TestClient(app)

        # Lets use EveHab's pre to start testing
        msg = eveHab.msgOwnEvent(sn=0)
        serder = serdering.SerderKERI(raw=msg)
        act = bytes(msg[serder.size :])

        rep = client.simulate_post(
            path="/receipts",
            body=serder.raw.decode("utf-8"),
            headers={CESR_ATTACHMENT_HEADER: act.decode("utf-8")},
        )
        assert rep.status == falcon.HTTP_BAD_REQUEST
        assert rep.json == {"title": "CESR request destination header missing"}

        rep = client.simulate_post(
            path="/witnesses", body=json.dumps({"aid": bobHab.pre})
        )
        assert rep.status == falcon.HTTP_OK
        data = rep.json
        assert data["cid"] == bobHab.pre
        bobWit = data["eid"]
        witness = witery.wits[bobWit]

        rep = client.simulate_post(
            path="/aids", body=msg, headers={"content-type": "application/cesr"}
        )
        assert rep.status == falcon.HTTP_400
        assert rep.json == {"title": "CESR request destination header missing"}

        rep = client.simulate_post(
            path="/aids",
            body=msg,
            headers={
                "content-type": "application/json",
                CESR_DESTINATION_HEADER: bobWit,
            },
        )
        assert rep.status == falcon.HTTP_UNSUPPORTED_MEDIA_TYPE
        assert rep.json == {
            "description": "application/json not accepted, must be multipart/form-data",
            "title": "415 Unsupported Media Type",
        }

        rep = client.simulate_post(
            path="/receipts",
            body=serder.raw.decode("utf-8"),
            headers={
                CESR_ATTACHMENT_HEADER: act.decode("utf-8"),
                CESR_DESTINATION_HEADER: bobWit,
            },
        )

        assert rep.status == falcon.HTTP_NOT_ACCEPTABLE
        assert rep.json == {
            "description": "Unacceptable content type.",
            "title": "Content type error",
        }

        # Now try it with bobHab's pre that is in the whitelist
        msg = bobHab.msgOwnEvent(sn=0)
        serder = serdering.SerderKERI(raw=msg)
        act = bytes(msg[serder.size :])
        rep = client.simulate_post(
            path="/receipts",
            body=serder.raw.decode("utf-8"),
            headers={
                CESR_ATTACHMENT_HEADER: act.decode("utf-8"),
                "content-type": CESR_CONTENT_TYPE,
                CESR_DESTINATION_HEADER: bobWit,
            },
        )

        assert rep.status == falcon.HTTP_PRECONDITION_FAILED
        assert rep.json == {
            "description": "AID=ENsqL5zLYNbZf0kcOlx-ioqNWlatD9rKZZM4hbEI7nza not "
            "initialized with 2-factor code",
            "title": "412 Precondition Failed",
        }

        # Send Serder without signatures
        body, headers = multipart.create(dict(kel=serder.raw + b"XXX"))
        rep = client.simulate_post(path="/aids", body=body, headers=headers)
        assert rep.status == falcon.HTTP_400
        assert rep.json == {"title": "CESR request destination header missing"}

        body, headers = multipart.create(dict(kel=msg))
        headers[CESR_DESTINATION_HEADER] = bobWit
        rep = client.simulate_post(path="/aids", body=body, headers=headers)
        assert rep.status == falcon.HTTP_200
        data = rep.json
        assert data["oobi"] == f"http://127.0.0.1:5632/oobi/{bobWit}/controller"
        code = data["totp"]

        # Decrypt and load the code from the response with Bob's hab
        m = coring.Matter(qb64=code)
        rcode = coring.Matter(qb64=bobHab.decrypt(m.raw)).raw

        # Decrypt and load the code from the database with Wan's hab
        cipher = safe.codes.get(
            keys=(
                bobHab.pre,
                bobWit,
            )
        )
        witHab = witness.hby.habs[bobWit]
        plain = witHab.decrypt(ser=cipher.raw)
        scode = coring.Matter(qb64b=plain).raw

        # Compare that the codes are the same.
        assert rcode == scode

        # ensure the code is valid for TOTP
        totp = pyotp.TOTP(rcode)
        assert totp is not None

        rot = bobHab.rotate(adds=[bobWit])

        serder = serdering.SerderKERI(raw=rot)
        act = rot[serder.size :]

        rep = client.simulate_post(
            path="/receipts",
            body=serder.raw.decode("utf-8"),
            headers={
                CESR_ATTACHMENT_HEADER: act.decode("utf-8"),
                "content-type": CESR_CONTENT_TYPE,
                "TOTP": "989561",
                CESR_DESTINATION_HEADER: bobWit,
            },
        )

        assert rep.status == falcon.HTTP_ACCEPTED
        rep = client.simulate_post(
            path="/receipts",
            body=serder.raw.decode("utf-8"),
            headers={
                CESR_ATTACHMENT_HEADER: act.decode("utf-8"),
                "content-type": CESR_CONTENT_TYPE,
                "Authorization": f"{totp.now()}#{helping.nowIso8601()}",
                CESR_DESTINATION_HEADER: bobWit,
            },
        )

        assert rep.status == falcon.HTTP_200
        rct = serdering.SerderKERI(raw=rep.content)
        assert rct.ked["t"] == "rct"
        assert rct.sn == 1
        assert rct.pre == bobHab.pre
        assert kering.deversify(rct.ked["v"]).pvrsn.major == 1

        # Fetch the same stored receipt back over GET and verify that receipt
        # lookup stays on the stored event's v1 body version while framing any
        # generated witness signatures in the modern v2 CESR attachment format.
        rep = client.simulate_get(
            "/receipts",
            query_string=f"pre={bobHab.pre}&sn=1",
            headers={CESR_DESTINATION_HEADER: bobWit},
        )
        assert rep.status == falcon.HTTP_200
        rct = serdering.SerderKERI(raw=rep.content)
        assert kering.deversify(rct.ked["v"]).pvrsn.major == 1
        atc = rep.content[len(rct.raw) :]
        assert counting.Counter(qb64b=atc).code == counting.CtrDex_2_0.WitnessIdxSigs


def test_receipts_post_and_get_follow_stored_v2_event_version(multipart):
    """Receipts should keep a v2 event's body version on both POST and GET."""
    with (
        habbing.openHab(
            name="bob-v2", salt=b"0123456789febob2", version=kering.Vrsn_2_0
        ) as (_, bobHab),
        habbing.openHab(
            name="wan-v2",
            transferable=False,
            salt=b"0123456789fecba2",
            version=kering.Vrsn_2_0,
        ) as (_, wanHab),
    ):
        _seed_endpoint_records(
            wanHab,
            url="http://127.0.0.1:5642/",
            version=wanHab.kever.serder.pvrsn,
        )
        _doist, witery = _start_witery(wanHab)

        app = falcon.App()
        app.add_route("/witnesses", witnessing.WitnessCollectionEnd(witery))
        aiding.loadEnds(app=app, witery=witery)
        app.add_route(
            "/receipts", indirecting.ReceiptEnd(witery=witery, aids=[bobHab.pre])
        )
        client = testing.TestClient(app)

        rep_w = client.simulate_post(
            path="/witnesses", body=json.dumps({"aid": bobHab.pre})
        )
        assert rep_w.status == falcon.HTTP_OK
        bob_wit = rep_w.json["eid"]
        witness = witery.wits[bob_wit]

        body, headers = multipart.create(dict(kel=bobHab.msgOwnEvent(sn=0)))
        headers[CESR_DESTINATION_HEADER] = bob_wit
        rep_a = client.simulate_post(path="/aids", body=body, headers=headers)
        assert rep_a.status == falcon.HTTP_200
        code = rep_a.json["totp"]
        matter = coring.Matter(qb64=code)
        raw_code = coring.Matter(qb64=bobHab.decrypt(matter.raw)).raw
        totp = pyotp.TOTP(raw_code)

        # Submit a real v2 rotation so the witness stores a fully witnessed
        # event and returns an immediate receipt in the same event version.
        rot = bobHab.rotate(adds=[bob_wit], version=kering.Vrsn_2_0)
        rot_serder = serdering.SerderKERI(raw=rot)
        rep_post = _simulate_cesr_post(
            client,
            path="/receipts",
            msg=rot,
            destination=bob_wit,
            headers={"Authorization": f"{totp.now()}#{helping.nowIso8601()}"},
        )
        assert rep_post.status == falcon.HTTP_200
        post_rct = serdering.SerderKERI(raw=rep_post.content)
        assert kering.deversify(post_rct.ked["v"]).pvrsn.major == 2

        row_wigs = witness.hab.db.wigs.get(
            keys=(bobHab.pre.encode("utf-8"), rot_serder.saidb)
        )
        assert len(row_wigs) >= 1

        # Lookup by sequence number and by said should both reconstruct the
        # same stored v2 receipt body while framing witness signatures in v2.
        hdrs = {CESR_DESTINATION_HEADER: bob_wit}
        rep_by_sn = client.simulate_get(
            "/receipts",
            query_string=f"pre={bobHab.pre}&sn=1",
            headers=hdrs,
        )
        assert rep_by_sn.status == falcon.HTTP_200
        assert rep_by_sn.headers["Content-Type"] == "application/json+cesr"
        rct_by_sn = serdering.SerderKERI(raw=rep_by_sn.content)
        assert rct_by_sn.ked["t"] == "rct"
        assert rct_by_sn.sn == 1
        assert kering.deversify(rct_by_sn.ked["v"]).pvrsn.major == 2
        atc_by_sn = rep_by_sn.content[len(rct_by_sn.raw) :]
        assert (
            counting.Counter(qb64b=atc_by_sn).code == counting.CtrDex_2_0.WitnessIdxSigs
        )

        rep_by_said = client.simulate_get(
            "/receipts",
            query_string=f"pre={bobHab.pre}&said={rot_serder.said}",
            headers=hdrs,
        )
        assert rep_by_said.status == falcon.HTTP_200
        rct_by_said = serdering.SerderKERI(raw=rep_by_said.content)
        assert rct_by_said.ked["t"] == "rct"
        assert rct_by_said.ked["d"] == rot_serder.said
        assert kering.deversify(rct_by_said.ked["v"]).pvrsn.major == 2
