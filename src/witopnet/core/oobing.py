# -*- encoding: utf-8 -*-

"""
KERI
witopnet.core.oobing package

"""

import falcon
from keri.core import eventing
from keri.end import ending
from ordered_set import OrderedSet as oset
from keri import kering


def _oobiReplying():
    """Return the fixed legacy reply settings used for OOBI discovery records.

    OOBI replies are discovery/bootstrap metadata, not permanent KEL history.
    We therefore keep fresh OOBI reply records on the stable legacy v1 JSON
    format even when the identifier's current key events are v2
    """
    return dict(
        version=kering.Vrsn_1_0,
        pvrsn=kering.Vrsn_1_0,
        kind=eventing.Kinds.json,
    )


def _legacySelfOobi(hab, role, eids):
    """Build an OOBI stream for a witness-owned identifier with legacy replies.

    The controller's replayed KEL is returned as-is so stored events keep
    their original wire version. The self-authored endpoint replies are rebuilt
    on demand as legacy v1 JSON discovery records because OOBI is a bootstrap
    surface, not a permanent protocol-history artifact.

    Parameters:
        hab (Hab): Local habitat that owns the identifier being served.
        role (str | None): Optional OOBI role filter from the request path.
        eids (list[str]): Optional endpoint identifier filter from the request path.

    Returns:
        bytearray: Replay plus freshly generated self-authored OOBI replies.
    """
    replying = _oobiReplying()
    msgs = bytearray(hab.replay(hab.pre))

    for (_, erole, eid), end in hab.db.ends.getTopItemIter(keys=(hab.pre,)):
        if not (end.enabled or end.allowed):
            continue
        if role is not None and role != erole:
            continue
        if eids and eid not in eids:
            continue

        # Only regenerate location replies we are authoritative for; foreign
        # endpoint locations must keep their originally authored bytes.
        if eid == hab.pre:
            msgs.extend(
                hab.replyLocScheme(
                    eid=eid,
                    **replying,
                )
            )
        else:
            msgs.extend(hab.loadLocScheme(eid=eid))

        msgs.extend(
            hab.makeEndRole(
                eid=eid,
                role=erole,
                allow=end.allowed,
                **replying,
            )
        )

    return msgs


class OOBIEnd:
    """REST API for OOBI endpoints

    Attributes:
        .hby (Habery): database access

    """

    def __init__(self, witery, default=None):
        """End point for responding to OOBIs

        Parameters:
            witery (Witnessery): database environment
            default (str) qb64 AID of the 'self' of the node for

        """
        self.witery = witery
        self.default = default

    def on_get(self, _, rep, aid=None, role=None, eid=None):
        """GET endoint for OOBI resource

        Parameters:
            _: Falcon request object
            rep: Falcon response object
            aid: qb64 identifier prefix of OOBI
            role: requested role for OOBI rpy message
            eid: qb64 identifier prefix of participant in role

        """
        if aid is None:
            if self.default is None:
                raise falcon.HTTPNotFound(description="no blind oobi for this node")

            aid = self.default

        if (witness := self.witery.lookup(aid)) is None:
            if eid is not None:
                witness = self.witery.lookup(eid)
            else:
                wits = self.witery.db.cids.get(keys=(aid,))
                if wits:
                    witness = self.witery.lookup(wits[0])

        if witness is None:
            raise falcon.HTTPNotFound(description=f"witness for aid {aid} not found")

        if aid not in witness.hby.kevers:
            raise falcon.HTTPNotFound(description=f"aid {aid} not found")

        kever = witness.hby.kevers[aid]
        db = witness.hby.db
        if not db.opened:
            raise falcon.HTTPNotFound(description=f"witness for aid {aid} not found")

        if not db.fullyWitnessed(kever.serder):
            raise falcon.HTTPNotFound(description=f"aid {aid} not found")

        # Replayed KEL events remain exactly as stored. Fresh discovery reply
        # records, stay on the simpler legacy v1 JSON format
        replying = _oobiReplying()

        owits = oset(kever.wits)
        if kever.prefixer.qb64 in witness.hby.prefixes:  # One of our identifiers
            hab = witness.hby.habs[kever.prefixer.qb64]
            own = True
        elif match := owits.intersection(
            witness.hby.prefixes
        ):  # We are a witness for identifier
            pre = match.pop()
            hab = witness.hby.habs[pre]
            own = False
        else:  # Not allowed to respond
            raise falcon.HTTPNotAcceptable(description="invalid OOBI request")

        eids = []
        if eid:
            eids.append(eid)

        if own and aid == hab.pre and role in (None, kering.Roles.controller):
            # Rebuild self-authored controller metadata in the fixed legacy
            # OOBI format; the replayed KEL remains in its stored version.
            msgs = _legacySelfOobi(hab=hab, role=role, eids=eids)
        else:
            msgs = hab.replyToOobi(
                aid=aid,
                role=role,
                eids=eids,
                **replying,
            )
            if not msgs and role is None:
                msgs = hab.replyToOobi(
                    aid=aid,
                    role=kering.Roles.witness,
                    eids=eids,
                    **replying,
                )
                msgs.extend(hab.replay(aid))

        if msgs:
            rep.status = falcon.HTTP_200  # This is the default status
            rep.set_header(ending.OOBI_AID_HEADER, aid)
            rep.content_type = "application/json+cesr"
            rep.data = bytes(msgs)

        else:
            rep.status = falcon.HTTP_NOT_FOUND
