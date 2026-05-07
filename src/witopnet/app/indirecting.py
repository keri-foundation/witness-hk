# -*- encoding: utf-8 -*-
"""
KERI
keri.app.indirecting module

simple indirect mode demo support classes
"""

import datetime
import time

import falcon
import pyotp
from hio.base import doing
from hio.help import decking
from keri import help
from keri.app import httping
from keri.app.httping import CESR_DESTINATION_HEADER
from keri.core import eventing, coring, serdering, counting
from keri.core.coring import Ilks
from keri.core.eventing import reply
from keri.help import helping

logger = help.ogler.getLogger()


class WitnessStart(doing.DoDoer):
    """Doer to print witness prefix after initialization"""

    def __init__(
        self,
        hab,
        parser,
        kvy,
        tvy,
        rvy,
        exc,
        cues=None,
        replies=None,
        responses=None,
        queries=None,
        **opts,
    ):
        self.hab = hab
        self.parser = parser
        self.kvy = kvy
        self.tvy = tvy
        self.rvy = rvy
        self.exc = exc
        self.queries = queries if queries is not None else decking.Deck()
        self.replies = replies if replies is not None else decking.Deck()
        self.responses = responses if responses is not None else decking.Deck()
        self.cues = cues if cues is not None else decking.Deck()

        doers = [
            doing.doify(self.start),
            doing.doify(self.msgDo),
            doing.doify(self.escrowDo),
            doing.doify(self.cueDo),
        ]
        super().__init__(doers=doers, **opts)

    def start(self, tymth=None, tock=0.0, **kwa):
        """Prints witness name and prefix

        Parameters:
            tymth (function): injected function wrapper closure returned by .tymen() of
                Tymist instance. Calling tymth() returns associated Tymist .tyme.
            tock (float): injected initial tock value

        """
        self.wind(tymth)
        self.tock = tock
        _ = yield self.tock

        while not self.hab.inited:
            yield self.tock

        logger.info(f"Witness {self.hab.name} : {self.hab.pre}")

    def msgDo(self, tymth=None, tock=0.0, **kwa):
        """
        Returns doifiable Doist compatibile generator method (doer dog) to process
            incoming message stream of .kevery

        Parameters:
            tymth (function): injected function wrapper closure returned by .tymen() of
                Tymist instance. Calling tymth() returns associated Tymist .tyme.
            tock (float): injected initial tock value

        Usage:
            add result of doify on this method to doers list
        """
        self.wind(tymth)
        self.tock = tock
        _ = yield self.tock

        if self.parser.ims:
            logger.info(
                "Client %s received:\n%s\n...\n", self.kvy, self.parser.ims[:1024]
            )
        done = yield from self.parser.parsator(
            local=True
        )  # process messages continuously
        return done  # should nover get here except forced close

    def escrowDo(self, tymth=None, tock=0.0, **kwa):
        """
         Returns doifiable Doist compatibile generator method (doer dog) to process
            .kevery and .tevery escrows.

        Parameters:
            tymth (function): injected function wrapper closure returned by .tymen() of
                Tymist instance. Calling tymth() returns associated Tymist .tyme.
            tock (float): injected initial tock value

        Usage:
            add result of doify on this method to doers list
        """
        self.wind(tymth)
        self.tock = tock
        _ = yield self.tock

        while True:
            self.kvy.processEscrows()
            self.rvy.processEscrowReply()
            if self.tvy is not None:
                self.tvy.processEscrows()
            self.exc.processEscrow()

            yield

    def cueDo(self, tymth=None, tock=0.0, **kwa):
        """
         Returns doifiable Doist compatibile generator method (doer dog) to process
            .kevery.cues deque

        Doist Injected Attributes:
            g.tock = tock  # default tock attributes
            g.done = None  # default done state
            g.opts

        Parameters:
            tymth: injected function wrapper closure returned by .tymen() of
                Tymist instance. Calling tymth() returns associated Tymist .tyme.
            tock: injected initial tock value

        Usage:
            add result of doify on this method to doers list
        """
        self.wind(tymth)
        self.tock = tock
        _ = yield self.tock

        while True:
            while self.cues:
                cue = self.cues.popleft()
                cueKin = cue["kin"]
                if cueKin == "stream":
                    self.queries.append(cue)
                else:
                    self.responses.append(cue)
                yield self.tock
            yield self.tock


class HttpEnd:
    """
    HTTP handler that accepts and KERI events POSTed as the body of a request with all attachments to
    the message as a CESR attachment HTTP header.  KEL Messages are processed and added to the database
    of the provided Habitat.

    This also handles `req`, `exn` and `tel` messages that respond with a KEL replay.
    """

    TimeoutQNF = 30
    TimeoutMBX = 5

    def __init__(self, witery, rxbs=None, mbx=None, qrycues=None):
        """
        Create the KEL HTTP server from the Habitat with an optional Falcon App to
        register the routes with.

        Parameters
             rxbs (bytearray): output queue of bytes for message processing
             mbx (Mailboxer): Mailbox storage
             qrycues (Deck): inbound qry response queues

        """
        self.witery = witery
        self.rxbs = rxbs if rxbs is not None else bytearray()

        self.mbx = mbx
        self.qrycues = qrycues if qrycues is not None else decking.Deck()

    def on_post(self, req, rep):
        """
        Handles POST for KERI event messages.

        Parameters:
              req (Request) Falcon HTTP request
              rep (Response) Falcon HTTP response

        ---
        summary:  Accept KERI events with attachment headers and parse
        description:  Accept KERI events with attachment headers and parse.
        tags:
           - Events
        requestBody:
           required: true
           content:
             application/json:
               schema:
                 type: object
                 description: KERI event message
        responses:
           200:
              description: Mailbox query response for server sent events
           204:
              description: KEL or EXN event accepted.
        """
        if req.method == "OPTIONS":
            rep.status = falcon.HTTP_200
            return

        if CESR_DESTINATION_HEADER not in req.headers:
            raise falcon.HTTPBadRequest(title="CESR request destination header missing")

        aid = req.headers[CESR_DESTINATION_HEADER]
        witness = self.witery.lookup(aid)
        if witness is None:
            raise falcon.HTTPNotFound(title=f"unknown destination AID {aid}")

        rep.set_header("Cache-Control", "no-cache")
        rep.set_header("connection", "close")

        cr = httping.parseCesrHttpRequest(req=req)
        sadder = coring.Sadder(ked=cr.payload, kind=eventing.Kinds.json)
        msg = bytearray(sadder.raw)
        msg.extend(cr.attachments.encode("utf-8"))

        if (cipher := witness.getCode()) is not None:

            plain = witness.hab.decrypt(ser=cipher.raw)
            scode = coring.Matter(qb64b=plain).raw
            # Check for a one-time-password in the Authroizaiton header.  If it works, parse this as "local"
            if (auth := req.get_header("Authorization")) is not None and validCode(
                scode, auth
            ):
                witness.parser.parseOne(ims=msg, local=True)
            else:  # Otherwise this is not from a trusted source, so parse it as not "local"
                witness.parser.parseOne(
                    ims=msg, local=False
                )  # This will likely go to the misfit escrow
        else:
            witness.parser.parseOne(
                ims=msg, local=False
            )  # This will likely go to the misfit escrow

        if sadder.proto in ("ACDC",):
            rep.set_header("Content-Type", "application/json")
            rep.status = falcon.HTTP_204
        else:
            ilk = sadder.ked["t"]
            if ilk in (
                Ilks.icp,
                Ilks.rot,
                Ilks.ixn,
                Ilks.dip,
                Ilks.drt,
                Ilks.exn,
                Ilks.rpy,
            ):
                rep.set_header("Content-Type", "application/json")
                rep.status = falcon.HTTP_204
            elif ilk in (Ilks.vcp, Ilks.vrt, Ilks.iss, Ilks.rev, Ilks.bis, Ilks.brv):
                rep.set_header("Content-Type", "application/json")
                rep.status = falcon.HTTP_204
            elif ilk in (Ilks.qry,):
                if sadder.ked["r"] in ("mbx",):
                    rep.set_header("Content-Type", "text/event-stream")
                    rep.status = falcon.HTTP_200
                    rep.stream = QryRpyMailboxIterable(
                        mbx=witness.mbx, cues=self.qrycues, said=sadder.said
                    )
                else:
                    rep.set_header("Content-Type", "application/json")
                    rep.status = falcon.HTTP_204

    def on_put(self, req, rep):
        """
        Handles PUT for KERI mbx event messages.

        Parameters:
              req (Request) Falcon HTTP request
              rep (Response) Falcon HTTP response

        ---
        summary:  Accept KERI events with attachment headers and parse
        description:  Accept KERI events with attachment headers and parse.
        tags:
           - Events
        requestBody:
           required: true
           content:
             application/json:
               schema:
                 type: object
                 description: KERI event message
        responses:
           200:
              description: Mailbox query response for server sent events
           204:
              description: KEL or EXN event accepted.
        """
        if req.method == "OPTIONS":
            rep.status = falcon.HTTP_200
            return

        rep.set_header("Cache-Control", "no-cache")
        rep.set_header("connection", "close")

        self.rxbs.extend(req.bounded_stream.read())

        rep.set_header("Content-Type", "application/json")
        rep.status = falcon.HTTP_204


class QryRpyMailboxIterable:
    """Iterable that waits for a query-reply cue matching a specific SAID,
    then delegates to a MailboxIterable for server-sent event streaming.

    Used as a Falcon response stream for mailbox query (``qry``/``mbx``) requests.
    Pulls cues from the shared query-reply deck until it finds one whose SAID
    matches the request, then wraps it in a MailboxIterable.
    """

    def __init__(self, cues, mbx, said, retry=5000):
        """
        Parameters:
            cues (Deck): shared deck of query-reply cue dicts
            mbx (Mailboxer): mailbox storage for the witness
            said (str): SAID of the query event this iterable is waiting for
            retry (int): SSE retry interval in milliseconds sent to the client
        """
        self.mbx = mbx
        self.retry = retry
        self.cues = cues
        self.said = said
        self.iter = None

    def __iter__(self):
        """Return self as the iterator."""
        return self

    def __next__(self):
        """Yield the next SSE chunk, or an empty bytes if still waiting for the cue.

        Returns:
            bytes: next server-sent event chunk, or ``b""`` while waiting
        """
        if self.iter is None:
            if self.cues:
                cue = self.cues.pull()  # self.cues.popleft()
                serder = cue["serder"]
                if serder.said == self.said:
                    kin = cue["kin"]
                    if kin == "stream":
                        self.iter = iter(
                            MailboxIterable(
                                mbx=self.mbx,
                                pre=cue["pre"],
                                topics=cue["topics"],
                                retry=self.retry,
                            )
                        )
                else:
                    self.cues.append(cue)

            return b""

        return next(self.iter)


class MailboxIterable:
    """Iterable that streams mailbox messages for a prefix as server-sent events.

    Polls the mailbox for new messages across all subscribed topics, yielding
    SSE-formatted chunks until ``TimeoutMBX`` milliseconds have elapsed since
    the last message was found.
    """

    TimeoutMBX = 30000000

    def __init__(self, mbx, pre, topics, retry=5000):
        """
        Parameters:
            mbx (Mailboxer): mailbox storage to read from
            pre (str): qb64 AID prefix whose mailbox to stream
            topics (dict): mapping of topic name to starting sequence number index
            retry (int): SSE retry interval in milliseconds sent to the client
        """
        self.mbx = mbx
        self.pre = pre
        self.topics = topics
        self.retry = retry

    def __iter__(self):
        """Initialize timing and return self as the iterator."""
        self.start = self.end = time.perf_counter()
        return self

    def __next__(self):
        """Yield the next SSE chunk, or raise StopIteration when the timeout expires.

        Returns:
            bytearray: next server-sent event chunk

        Raises:
            StopIteration: when no new messages have arrived within TimeoutMBX
        """
        if self.end - self.start < self.TimeoutMBX:
            if self.start == self.end:
                self.end = time.perf_counter()
                return bytearray(f"retry: {self.retry}\n\n".encode("utf-8"))

            data = bytearray()
            for topic, idx in self.topics.items():
                key = self.pre + topic
                for fn, _, msg in self.mbx.cloneTopicIter(key, idx):
                    data.extend(
                        bytearray(
                            "id: {}\nevent: {}\nretry: {}\ndata: ".format(
                                fn, topic, self.retry
                            ).encode("utf-8")
                        )
                    )
                    data.extend(msg)
                    data.extend(b"\n\n")
                    idx = idx + 1
                    self.start = time.perf_counter()

                self.topics[topic] = idx
            self.end = time.perf_counter()
            return data

        raise StopIteration


class ReceiptEnd:
    """Endpoint class for Witnessing receipting functionality

    Most times a witness will be able to return its receipt for an event inband.  This API
    will provide that functionality.  When an event needs to be escrowed, this POST API
    will return a 202 and also provides a generic GET API for retrieving a receipt for any
    event.

    """

    def __init__(self, witery, inbound=None, outbound=None, aids=None):
        """
        Parameters:
            witery (Witnessery): registry of active witness instances
            inbound (Deck | None): inbound message queue
            outbound (Deck | None): outbound message queue
            aids (list | None): optional allowlist of controller AIDs; if None,
                all AIDs known to the witness are accepted
        """
        self.witery = witery
        self.inbound = inbound if inbound is not None else decking.Deck()
        self.outbound = outbound if outbound is not None else decking.Deck()
        self.aids = aids
        self.receipts = set()

    def on_post(self, req, rep):
        """Receipt POST endpoint handler

        Parameters:
            req (Request): Falcon HTTP request object
            rep (Response): Falcon HTTP response object

        """
        if CESR_DESTINATION_HEADER not in req.headers:
            raise falcon.HTTPBadRequest(title="CESR request destination header missing")

        aid = req.headers[CESR_DESTINATION_HEADER]

        witness = self.witery.lookup(aid)
        if witness is None:
            raise falcon.HTTPBadRequest(description=f"AID {aid} is not recognized")

        if req.method == "OPTIONS":
            rep.status = falcon.HTTP_200
            return

        rep.set_header("Cache-Control", "no-cache")
        rep.set_header("connection", "close")

        cr = httping.parseCesrHttpRequest(req=req)
        serder = serdering.SerderKERI(sad=cr.payload, kind=eventing.Kinds.json)

        pre = serder.ked["i"]
        if witness.aids is not None and pre not in witness.aids:
            raise falcon.HTTPForbidden(
                description=f"invalid AID={pre} for witnessing receipting"
            )

        if (cipher := witness.getCode()) is None:
            raise falcon.HTTPPreconditionFailed(
                description=f"AID={pre} not initialized with 2-factor code"
            )

        plain = witness.hab.decrypt(ser=cipher.raw)
        scode = coring.Matter(qb64b=plain).raw

        ilk = serder.ked["t"]
        if ilk not in (Ilks.icp, Ilks.rot, Ilks.ixn, Ilks.dip, Ilks.drt):
            raise falcon.HTTPBadRequest(
                description=f"invalid event type ({ilk}) for receipting"
            )

        msg = bytearray(serder.raw)
        msg.extend(cr.attachments.encode("utf-8"))

        # Check for a one-time-password in the Authroizaiton header.  If it works, parse this as "local"
        if (auth := req.get_header("Authorization")) is not None and validCode(
            scode, auth
        ):
            witness.parser.parseOne(ims=msg, local=True)
        else:  # Otherwise this is not form a trusted source, so parse it as not "local"
            witness.parser.parseOne(
                ims=msg, local=False
            )  # This will likely go to the misfit escrow

        if pre in witness.hab.kevers and witness.hab.kevers[pre].sn == serder.sn:
            kever = witness.hab.kevers[pre]
            wits = kever.wits

            if witness.hab.pre not in wits:
                raise falcon.HTTPBadRequest(
                    description=f"{witness.hab.pre} is not a valid witness for {pre} event at "
                    f"{serder.sn}: wits={wits}"
                )

            rct = witness.hab.receipt(serder)

            witness.parser.parseOne(bytes(rct))

            saids = witness.hab.db.misfits.get(keys=(serder.pre, serder.snh))
            if saids:
                witness.hab.db.misfits.rem(keys=(serder.pre, serder.snh))

            rep.set_header("Content-Type", "application/json+cesr")
            rep.status = falcon.HTTP_200
            rep.data = bytes(rct)
        else:
            rep.status = falcon.HTTP_202

    def on_get(self, req, rep):
        """Receipt GET endpoint handler

        Parameters:
            req (Request): Falcon HTTP request object
            rep (Response): Falcon HTTP response object

        """
        if CESR_DESTINATION_HEADER not in req.headers:
            raise falcon.HTTPBadRequest(title="CESR request destination header missing")

        aid = req.headers[CESR_DESTINATION_HEADER]

        witness = self.witery.lookup(aid)
        if witness is None:
            raise falcon.HTTPBadRequest(description=f"AID {aid} is not recognized")

        pre = req.get_param("pre")
        sn = req.get_param_as_int("sn")
        said = req.get_param("said")

        if pre is None:
            raise falcon.HTTPBadRequest(description="query param 'pre' is required")

        preb = pre.encode("utf-8")

        if sn is None and said is None:
            raise falcon.HTTPBadRequest(
                description="either 'sn' or 'said' query param is required"
            )

        if sn is not None:
            said = witness.hab.db.kels.getLast(keys=preb, on=sn)

        if said is None:
            raise falcon.HTTPNotFound(
                description=f"event for {pre} at {sn} ({said}) not found"
            )

        saidb = said.encode("utf-8") if isinstance(said, str) else bytes(said)
        if not (serder := witness.hab.db.evts.get(keys=(preb, saidb))):
            raise falcon.HTTPNotFound(
                description="Missing event for dig={}.".format(saidb)
            )
        if serder.sn > 0:
            wits = [
                wit.qb64 for wit in witness.hab.kvy.fetchWitnessState(pre, serder.sn)
            ]
        else:
            wits = serder.ked["b"]

        if witness.hab.pre not in wits:
            raise falcon.HTTPBadRequest(
                description=f"{witness.hab.pre} is not a valid witness for {pre} event at "
                f"{serder.sn}, {wits}"
            )
        rserder = eventing.receipt(pre=pre, sn=sn, said=saidb.decode("utf-8"))
        rct = bytearray(rserder.raw)
        if wigers := witness.hab.db.wigs.get(keys=(preb, saidb)):
            rct.extend(
                counting.Counter(
                    code=counting.CtrDex_1_0.WitnessIdxSigs, count=len(wigers)
                ).qb64b
            )
            for wiger in wigers:
                rct.extend(wiger.qb64b)

        rep.set_header("Content-Type", "application/json+cesr")
        rep.status = falcon.HTTP_200
        rep.data = rct


class KeyStateEnd:
    """Key State Notice (KSN) query endpoint handler (GET /ksn)."""

    def __init__(self, witery):
        """
        Parameters:
            witery (Witnessery): registry of active witness instances
        """
        self.witery = witery

    def on_get(self, req, rep):
        """Return the fully-witnessed key state notice for a prefix.

        Parameters:
            req (Request): Falcon HTTP request object. Query params:
                - ``pre`` (str): qb64 AID prefix to query
            rep (Response): Falcon HTTP response object

        Raises:
            falcon.HTTPBadRequest: if the CESR destination header is missing or
                the AID is unrecognized
            falcon.HTTPNotFound: if the prefix is unknown or does not yet have a
                full complement of witness receipts
        """
        if CESR_DESTINATION_HEADER not in req.headers:
            raise falcon.HTTPBadRequest(title="CESR request destination header missing")

        aid = req.headers[CESR_DESTINATION_HEADER]

        witness = self.witery.lookup(aid)
        if witness is None:
            raise falcon.HTTPBadRequest(description=f"AID {aid} is not recognized")

        pre = req.get_param("pre")

        if pre not in witness.hab.kevers:
            msg = f"Query not found error on event pre={pre}"
            logger.debug(msg)
            raise falcon.HTTPNotFound(title="AID not found", description=msg)

        kever = witness.hab.kevers[pre]

        # get list of witness signatures to ensure we are presenting a fully witnessed event
        wigers = witness.hab.db.wigs.get(keys=(pre.encode("utf-8"), kever.serder.saidb))

        if len(wigers) < kever.toader.num:
            msg = f"Witness receipts not found error on event pre={pre}"
            logger.debug(msg)
            raise falcon.HTTPNotFound(
                title="Witness receipts not found", description=msg
            )

        rserder = reply(route=f"/ksn/{witness.hab.pre}", data=kever.state()._asdict())

        atc = witness.hab.endorse(rserder)
        rep.set_header("Content-Type", "application/cesr")
        rep.status = falcon.HTTP_200
        rep.data = atc


class KeyLogEnd:
    """Key Event Log (KEL) replay endpoint handler (GET /log)."""

    def __init__(self, witery):
        """
        Parameters:
            witery (Witnessery): registry of active witness instances
        """
        self.witery = witery

    def on_get(self, req, rep):
        """Replay KEL events for a prefix from a given first-seen sequence number.

        Parameters:
            req (Request): Falcon HTTP request object. Query params:
                - ``pre`` (str): qb64 AID prefix to replay
                - ``a`` (str, optional): anchor seal to wait for before replying
                - ``s`` (str, optional): hex sequence number to wait for before replying
                - ``fn`` (str, optional): hex first-seen sequence number to start from
                  (default ``0``)
            rep (Response): Falcon HTTP response object

        Raises:
            falcon.HTTPBadRequest: if the CESR destination header is missing or
                the AID is unrecognized
            falcon.HTTPNotFound: if the prefix is unknown, the requested sequence
                number or anchor is not yet fully witnessed, or no events exist
        """
        if CESR_DESTINATION_HEADER not in req.headers:
            raise falcon.HTTPBadRequest(title="CESR request destination header missing")

        aid = req.headers[CESR_DESTINATION_HEADER]

        witness = self.witery.lookup(aid)
        if witness is None:
            raise falcon.HTTPBadRequest(description=f"AID {aid} is not recognized")

        pre = req.get_param("pre")

        anchor = req.get_param("a", None)
        sn = req.get_param("s", None)
        sn = int(sn, 16) if sn else None
        fn = req.get_param("fn", None)
        fn = int(fn, 16) if fn else 0

        if pre not in witness.hab.kevers:
            msg = f"Query not found error on pre={pre}"
            logger.debug(msg)
            raise falcon.HTTPNotFound(title="AID not found", description=msg)

        kever = witness.hab.kevers[pre]
        if anchor:
            if not witness.hab.db.fetchAllSealingEventByEventSeal(pre=pre, seal=anchor):
                msg = f"Query not found error on pre={pre} and anchor={anchor}"
                logger.debug(msg)
                raise falcon.HTTPNotFound(title="AID not found", description=msg)

        elif sn is not None:
            if kever.sner.num < sn or not witness.hab.db.fullyWitnessed(kever.serder):
                msg = f"Query not found error on pre={pre} and sn={sn}"
                logger.debug(msg)
                raise falcon.HTTPNotFound(title="AID not found", description=msg)

        msgs = bytearray()  # outgoing messages
        for msg in witness.hab.db.clonePreIter(pre=pre, fn=fn):
            msgs.extend(msg)

        if kever.delpre:
            cloner = witness.hab.db.clonePreIter(
                pre=kever.delpre, fn=0
            )  # create iterator at 0
            for msg in cloner:
                msgs.extend(msg)

        if not msgs:
            msg = f"No events found on pre={pre}"
            logger.debug(msg)
            raise falcon.HTTPNotFound(title="AID not found", description=msg)

        rep.set_header("Content-Type", "application/cesr")
        rep.status = falcon.HTTP_200
        rep.data = bytes(msgs)


def validCode(scode, auth):
    """Validate a TOTP authorization code from an HTTP Authorization header.

    The Authorization header value must be in the format ``<otp>#<iso8601-datetime>``,
    where ``<otp>`` is a six-digit TOTP value and ``<iso8601-datetime>`` is the
    ISO 8601 timestamp used to generate it. The timestamp must be within the last
    10 minutes.

    Parameters:
        scode (bytes): raw TOTP secret bytes
        auth (str): Authorization header value in the format ``<otp>#<iso8601-datetime>``

    Returns:
        bool: True if the OTP is valid for the given time and the timestamp is
            not older than 10 minutes; False otherwise
    """
    otp, dtstr = auth.split("#")
    dt = helping.fromIso8601(dtstr)
    if dt < (helping.nowUTC() - datetime.timedelta(minutes=10)):
        return False

    return pyotp.TOTP(scode).verify(otp, for_time=dt)
