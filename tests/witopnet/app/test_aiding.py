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
from keri.core import coring, serdering
from keri.help import helping

from witopnet.app import aiding, indirecting
from witopnet.core import basing, witnessing


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

        doist = doing.Doist(limit=1.0, tock=0.03125, real=True)
        safe = basing.Baser(name=wanHab.name, temp=wanHab.temp)
        witery = witnessing.Witnessery(db=safe, temp=wanHab.temp)
        deeds = doist.enter(doers=[witery])
        doist.recur(deeds=deeds)

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

        kel = bobHab.makeOwnEvent(sn=0)
        serder = serdering.SerderKERI(raw=kel)
        assert kering.deversify(serder.ked["v"]).pvrsn.major == 1

        body, headers = multipart.create(dict(kel=kel))
        headers[CESR_DESTINATION_HEADER] = bob_wit
        rep = client.simulate_post(path="/aids", body=body, headers=headers)
        assert rep.status == falcon.HTTP_200
        assert "totp" in rep.json and "oobi" in rep.json
        assert bobHab.pre in witness.hab.kevers


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
        msg = eveHab.makeOwnEvent(sn=0)
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
        msg = bobHab.makeOwnEvent(sn=0)
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


def test_receipts_integration(multipart):
    """GET /receipts after a witnessed rotation: pre+sn, pre+said, parsed receipt body, witness.parser.version."""
    with (
        habbing.openHab(name="bob", salt=b"0123456789fedbob") as (_, bobHab),
        habbing.openHab(name="wan", transferable=False, salt=b"0123456789fedcba") as (
            _,
            wanHab,
        ),
    ):
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

        doist = doing.Doist(limit=1.0, tock=0.03125, real=True)
        safe = basing.Baser(name=wanHab.name, temp=wanHab.temp)
        witery = witnessing.Witnessery(db=safe, temp=wanHab.temp)
        deeds = doist.enter(doers=[witery])
        doist.recur(deeds=deeds)

        app = falcon.App()
        app.add_route("/witnesses", witnessing.WitnessCollectionEnd(witery))
        aiding.loadEnds(app=app, witery=witery)
        receipt_end = indirecting.ReceiptEnd(witery=witery, aids=[bobHab.pre])
        app.add_route("/receipts", receipt_end)
        client = testing.TestClient(app)

        rep_w = client.simulate_post(
            path="/witnesses", body=json.dumps({"aid": bobHab.pre})
        )
        assert rep_w.status == falcon.HTTP_OK
        bob_wit = rep_w.json["eid"]
        witness = witery.wits[bob_wit]

        icp = bobHab.makeOwnEvent(sn=0)
        body, headers = multipart.create(dict(kel=icp))
        headers[CESR_DESTINATION_HEADER] = bob_wit
        rep_a = client.simulate_post(path="/aids", body=body, headers=headers)
        assert rep_a.status == falcon.HTTP_200
        code = rep_a.json["totp"]
        m = coring.Matter(qb64=code)
        rcode = coring.Matter(qb64=bobHab.decrypt(m.raw)).raw
        totp = pyotp.TOTP(rcode)

        rot = bobHab.rotate(adds=[bob_wit])
        rot_serder = serdering.SerderKERI(raw=rot)
        act = rot[rot_serder.size :]
        rep_p = client.simulate_post(
            path="/receipts",
            body=rot_serder.raw.decode("utf-8"),
            headers={
                CESR_ATTACHMENT_HEADER: act.decode("utf-8"),
                "content-type": CESR_CONTENT_TYPE,
                "Authorization": f"{totp.now()}#{helping.nowIso8601()}",
                CESR_DESTINATION_HEADER: bob_wit,
            },
        )
        assert rep_p.status == falcon.HTTP_200

        preb = bobHab.pre.encode("utf-8")
        row_wigs = witness.hab.db.wigs.get(keys=(preb, rot_serder.saidb))
        assert len(row_wigs) >= 1

        hdrs = {CESR_DESTINATION_HEADER: bob_wit}
        rep_g1 = client.simulate_get(
            "/receipts",
            query_string=f"pre={bobHab.pre}&sn=1",
            headers=hdrs,
        )
        assert rep_g1.status == falcon.HTTP_200
        assert rep_g1.headers["Content-Type"] == "application/json+cesr"
        rct_sn = serdering.SerderKERI(raw=rep_g1.content)
        assert rct_sn.ked["t"] == "rct"
        assert rct_sn.sn == 1
        assert len(rep_g1.content) > len(rct_sn.raw)

        rep_g2 = client.simulate_get(
            "/receipts",
            query_string=f"pre={bobHab.pre}&said={rot_serder.said}",
            headers=hdrs,
        )
        assert rep_g2.status == falcon.HTTP_200
        rct_said = serdering.SerderKERI(raw=rep_g2.content)
        assert rct_said.ked["t"] == "rct"
        assert rct_said.ked["d"] == rot_serder.said
        assert len(rep_g2.content) > len(rct_said.raw)
