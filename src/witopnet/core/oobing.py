# -*- encoding: utf-8 -*-

"""
KERI
witopnet.core.oobing package

"""

import falcon
from keri import kering
from keri.end import ending
from ordered_set import OrderedSet as oset


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
            raise falcon.HTTPNotFound(description=f"winess for aid {aid} not found")

        if aid not in witness.hby.kevers:
            raise falcon.HTTPNotFound(description=f"aid {aid} not found")

        kever = witness.hby.kevers[aid]
        if not witness.hby.db.fullyWitnessed(kever.serder):
            raise falcon.HTTPNotFound(description=f"aid {aid} not found")

        owits = oset(kever.wits)
        if kever.prefixer.qb64 in witness.hby.prefixes:  # One of our identifiers
            hab = witness.hby.habs[kever.prefixer.qb64]
        elif match := owits.intersection(
            witness.hby.prefixes
        ):  # We are a witness for identifier
            pre = match.pop()
            hab = witness.hby.habs[pre]
        else:  # Not allowed to respond
            raise falcon.HTTPNotAcceptable(description="invalid OOBI request")

        eids = []
        if eid:
            eids.append(eid)

        msgs = hab.replyToOobi(aid=aid, role=role, eids=eids)
        if not msgs and role is None:
            msgs = hab.replyToOobi(aid=aid, role=kering.Roles.witness, eids=eids)
            msgs.extend(hab.replay(aid))

        if msgs:
            rep.status = falcon.HTTP_200  # This is the default status
            rep.set_header(ending.OOBI_AID_HEADER, aid)
            rep.content_type = "application/json+cesr"
            rep.data = bytes(msgs)

        else:
            rep.status = falcon.HTTP_NOT_FOUND
