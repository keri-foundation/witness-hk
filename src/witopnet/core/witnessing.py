# -*- encoding: utf-8 -*-

"""
KERI
witopnet.core.witnessing package

Core module for the Witness Operational Network. Provides the ``setup``
factory function, the ``Witnessery`` manager, and the ``Witness`` doer that
together implement the full lifecycle of a KERI witness service.
"""

import json
from urllib.parse import urlsplit

import falcon
from hio.base import doing
from hio.core import http
from hio.help import decking
from keri import kering, core, help
from keri.app import habbing, storing, forwarding, configing
from keri.app.httping import Clienter
from keri.app.indirecting import createHttpServer
from keri.app.oobiing import Oobiery
from keri.core import coring, routing, eventing, parsing
from keri.db.basing import BaserDoer
from keri.help import helping
from keri.peer import exchanging
from keri.vdr import verifying
from keri.vdr.eventing import Reger, Tevery

from witopnet.app import indirecting, aiding
from witopnet.app.indirecting import HttpEnd, ReceiptEnd, KeyStateEnd, KeyLogEnd
from witopnet.core import httping, basing, oobing

logger = help.ogler.getLogger()


def setup(
    bootHost="127.0.0.1",
    bootPort=5631,
    base=None,
    temp=False,
    headDirPath=None,
    host="127.0.0.1",
    port=5632,
    keypath=None,
    certpath=None,
    cafilepath=None,
):
    """Initialize and return the list of doers for the Witness Operational Network.

    Sets up a dual-server HTTP architecture:

    - **Boot server** (``bootHost:bootPort``): management API for provisioning
      and deleting witnesses, plus a ``/health`` liveness endpoint.
    - **Witness server** (``host:port``): KERI event processing, receipting,
      OOBI resolution, key-state queries, and KEL replay.

    Routes registered on the boot server:

    - ``POST /witnesses`` — provision a new witness
    - ``DELETE /witnesses/{eid}`` — delete a witness
    - ``GET /health`` — liveness probe

    Routes registered on the witness server:

    - ``GET /oobi[/{aid}[/{role}[/{eid}]]]`` — OOBI resolution
    - ``POST /`` — KERI event ingestion
    - ``POST /receipts`` — receipting endpoint
    - ``POST /aids`` — AID authentication registration
    - ``GET /ksn`` — key-state notice query
    - ``GET /log`` — KEL replay

    Parameters:
        bootHost (str): host the boot/management HTTP server listens on.
            Defaults to ``"127.0.0.1"``.
        bootPort (int): port the boot/management HTTP server listens on.
            Defaults to ``5631``.
        base (str | None): optional path prefix for KERI keystore storage.
        temp (bool): if True, use temporary in-memory databases (for testing).
        headDirPath (str | None): optional override for the config file directory.
        host (str): host the main witness HTTP server listens on.
            Defaults to ``"127.0.0.1"``.
        port (int): port the main witness HTTP server listens on.
            Defaults to ``5632``.
        keypath (str | None): path to TLS private key file; if None, plain HTTP is used.
        certpath (str | None): path to TLS certificate file.
        cafilepath (str | None): path to TLS CA bundle file.

    Returns:
        list: doers ready to be passed to a :class:`hio.base.doing.Doist` event loop.
    """
    db = basing.Baser(name="witopnet", base=base)
    dbDoer = BaserDoer(db)
    cf = configing.Configer(name=db.name, headDirPath=headDirPath)
    qrycues = decking.Deck()
    witery = Witnessery(db=db, base=base, temp=temp, qrycues=qrycues, cf=cf)

    doers = [witery]

    bootApp = falcon.App(
        middleware=falcon.CORSMiddleware(
            allow_origins="*",
            allow_credentials="*",
            expose_headers=[
                "cesr-attachment",
                "cesr-date",
                "content-type",
                "signature",
                "signature-input",
                "signify-resource",
                "signify-timestamp",
            ],
        )
    )

    bootServer = createHttpServer(
        host=bootHost,
        port=bootPort,
        app=bootApp,
        keypath=keypath,
        certpath=certpath,
        cafilepath=cafilepath,
    )
    bootSrvrDoer = http.ServerDoer(server=bootServer)

    witColEnd = WitnessCollectionEnd(witery)
    bootApp.add_route("/witnesses", witColEnd)

    witResEnd = WitnessResourceEnd(witery)
    bootApp.add_route("/witnesses/{eid}", witResEnd)

    healthEnd = HealthEnd()
    bootApp.add_route("/health", healthEnd)

    app = falcon.App(
        middleware=falcon.CORSMiddleware(
            allow_origins="*",
            allow_credentials="*",
            expose_headers=[
                "cesr-attachment",
                "cesr-date",
                "content-type",
                "signature",
                "signature-input",
                "signify-resource",
                "signify-timestamp",
            ],
        )
    )

    server = createHttpServer(
        host=host,
        port=port,
        app=app,
        keypath=keypath,
        certpath=certpath,
        cafilepath=cafilepath,
    )
    srvrDoer = http.ServerDoer(server=server)

    oobiEnd = oobing.OOBIEnd(witery=witery)
    app.add_route("/oobi", oobiEnd)
    app.add_route("/oobi/{aid}", oobiEnd)
    app.add_route("/oobi/{aid}/{role}", oobiEnd)
    app.add_route("/oobi/{aid}/{role}/{eid}", oobiEnd)

    httpEnd = HttpEnd(witery=witery, qrycues=qrycues)
    app.add_route("/", httpEnd)
    receiptEnd = ReceiptEnd(witery=witery)
    app.add_route("/receipts", receiptEnd)
    aiding.loadEnds(app, witery=witery)

    ksnEnd = KeyStateEnd(witery=witery)
    app.add_route("/ksn", ksnEnd)
    klogEnd = KeyLogEnd(witery=witery)
    app.add_route("/log", klogEnd)

    doers.extend([bootSrvrDoer, srvrDoer, dbDoer])  # type: ignore
    return doers


class Witnessery(doing.DoDoer):
    """Manages the lifecycle of all active :class:`Witness` instances.

    Reads witness records from the witopnet database on startup and instantiates
    a :class:`Witness` DoDoer for each. Exposes lookup, creation, and deletion
    of witnesses for use by the boot HTTP API.

    Attributes:
        db (Baser): witopnet LMDB database.
        base (str): path prefix for KERI keystore storage.
        temp (bool): whether keystores are temporary (in-memory).
        cf (Configer | None): KERI configuration file reader.
        scheme (str): URL scheme advertised by this witness service.
        host (str): hostname advertised in OOBI URLs.
        port (int | None): port advertised in OOBI URLs; None for default ports.
        qrycues (Deck): shared deck for query-reply cues.
        wits (dict): mapping of witness AID (str) to :class:`Witness` instance.
    """

    def __init__(
        self,
        db,
        base="",
        temp=False,
        cf=None,
        headDirPath=None,
        scheme=kering.Schemes.http,
        qrycues=None,
        host="127.0.0.1",
        port=5632,
    ):
        """
        Parameters:
            db (Baser): witopnet LMDB database.
            base (str): optional path prefix for KERI keystore storage.
            temp (bool): if True, use temporary in-memory keystores.
            cf (Configer | None): KERI configuration file reader; if provided,
                host/port/scheme are overridden by the ``witopnet.curls`` config value.
            headDirPath (str | None): optional override for the keystore head directory.
            scheme (str): URL scheme advertised by this witness (``"http"`` or
                ``"https"``). Defaults to ``kering.Schemes.http``.
            qrycues (Deck | None): shared deck for query-reply cues; a new
                :class:`hio.help.decking.Deck` is created if None.
            host (str): hostname advertised in OOBI URLs. Defaults to ``"127.0.0.1"``.
            port (int): port advertised in OOBI URLs. Defaults to ``5632``.
        """
        self.db = db
        self.base = base
        self.temp = temp
        self.headPathDir = headDirPath
        self.cf = cf
        self.scheme = scheme
        self.host = host
        self.port = port

        if self.cf is not None:
            conf = self.cf.get()
            conf = conf["witopnet"]
            if "dt" in conf:  # datetime of config file
                if "curls" in conf:
                    curls = conf["curls"]
                    url = curls[0]
                    splits = urlsplit(url)
                    self.host = splits.hostname
                    self.port = splits.port
                    self.scheme = (
                        splits.scheme
                        if splits.scheme in kering.Schemes
                        else kering.Schemes.http
                    )

        if (self.scheme == kering.Schemes.http and self.port == 80) or (
            self.scheme == kering.Schemes.https and self.port == 443
        ):
            self.port = None

        self.qrycues = qrycues if qrycues is not None else decking.Deck()
        self.wits = dict()

        self.reload()
        doers = list(self.wits.values())

        super(Witnessery, self).__init__(doers=doers, always=True)

    def reload(self):
        """Load all witness records from the database and instantiate Witness doers.

        Called once during ``__init__``. Iterates over every :class:`~witopnet.core.basing.Wit`
        record in the database and creates a :class:`Witness` for each.
        """
        for _keys, wit in self.db.wits.getTopItemIter():
            hby = habbing.Habery(
                name=wit.name,
                base=self.base,
                temp=self.temp,
                headDirPath=self.headPathDir,
            )
            hab = hby.habByName(wit.name)

            witness = Witness(
                witery=self, hby=hby, hab=hab, aid=wit.cid, qrycues=self.qrycues
            )
            self.wits[hab.pre] = witness

    def lookup(self, aid):
        """Return the :class:`Witness` for the given AID, or None if not found.

        Parameters:
            aid (str): qb64 AID of the witness or its associated controller.

        Returns:
            Witness | None: the matching :class:`Witness` instance, or ``None``.
        """
        if aid in self.wits:
            return self.wits[aid]

        return None

    @property
    def url(self):
        """Base URL advertised by this witness service (``scheme://host[:port]``).

        Standard ports (80 for HTTP, 443 for HTTPS) are omitted from the URL.

        Returns:
            str: base URL string, e.g. ``"http://127.0.0.1:5632"``.
        """
        if self.port is None:
            return f"{self.scheme}://{self.host}"
        else:
            return f"{self.scheme}://{self.host}:{self.port}"

    def createWitness(self, aid):
        """Provision a new :class:`Witness` for the given controller AID.

        Generates a new non-transferable signing identifier (hab), registers its
        endpoint role and URL scheme in the keystore, persists the witness record
        to the database, and adds the new :class:`Witness` to the running doer set.

        Parameters:
            aid (str): qb64 AID of the controller to be witnessed.

        Returns:
            Witness: the newly created and running :class:`Witness` instance.
        """
        # Create a random name from Salter
        name = core.Salter().qb64

        # We need to manage keys from an HSM here
        hby = habbing.Habery(
            name=name, base=self.base, headDirPath=self.headPathDir, bran=None
        )
        hab = hby.makeHab(name=name, transferable=False)
        dt = helping.nowIso8601()

        msgs = bytearray()
        msgs.extend(
            hab.makeEndRole(eid=hab.pre, role=kering.Roles.controller, stamp=dt)
        )
        msgs.extend(hab.makeLocScheme(url=self.url, scheme=self.scheme, stamp=dt))
        hab.psr.parse(ims=msgs)

        wit = basing.Wit(name=name, cid=aid, eid=hab.pre)

        self.db.wits.pin(keys=(hab.pre,), val=wit)
        self.db.cids.add(keys=(aid,), val=hab.kever.prefixer.qb64)

        witness = Witness(witery=self, hby=hby, hab=hab, aid=aid, qrycues=self.qrycues)
        self.wits[hab.pre] = witness

        self.extend([witness])

        return witness

    def deleteWitness(self, eid):
        """Remove and permanently destroy a running :class:`Witness`.

        Removes the witness record from the database, closes and clears its
        keystore, and removes its doer from the running set. This operation is
        irreversible — the keystore is deleted from disk.

        Parameters:
            eid (str): qb64 AID of the witness to delete.

        Raises:
            ValueError: if ``eid`` does not correspond to a known witness.
        """
        if eid not in self.wits:
            raise ValueError(
                f"Unable to delete witness, {eid} is not a valid witness identifier"
            )

        witness = self.wits.pop(eid)

        aid = witness.aids[0]
        self.db.wits.rem(keys=(eid,))
        self.db.cids.rem(keys=(aid,), val=eid)
        self.remove([witness])
        witness.hby.close(clear=True)


class Witness(doing.DoDoer):
    """DoDoer encapsulating all async processing for a single KERI witness.

    Owns the witness's :class:`~keri.app.habbing.Habery`, :class:`~keri.app.habbing.Hab`,
    parser, verifier, mailbox, and all associated doers (respondant, OOBI resolver,
    witness start). Manages the TOTP authentication code lifecycle for receipting.

    Attributes:
        witery (Witnessery): parent :class:`Witnessery` managing this witness.
        hby (Habery): KERI keystore environment for this witness.
        hab (Hab): KERI signing identifier (non-transferable) for this witness.
        aids (list[str]): list of controller AIDs this witness serves (currently one).
        mbx (Mailboxer): mailbox storage for witness messages.
        parser (Parser): KERI event parser shared by the HTTP endpoints.
        reger (Reger): verifiable credential registry database.
    """

    def __init__(self, witery, hby, hab, aid, qrycues):
        """
        Parameters:
            witery (Witnessery): parent :class:`Witnessery` managing this witness.
            hby (Habery): KERI keystore environment for this witness.
            hab (Hab): KERI signing identifier (non-transferable) for this witness.
            aid (str): qb64 controller AID this witness is assigned to.
            qrycues (Deck): shared deck for routing query-reply responses.
        """
        self.witery = witery
        self.hby = hby
        self.hab = hab
        self.aids = [aid]

        cues = decking.Deck()
        doers = []

        self.reger = Reger(name=hab.name, db=hab.db, temp=False)
        verfer = verifying.Verifier(hby=hby, reger=self.reger)

        self.mbx = storing.Mailboxer(name=hab.name, temp=hby.temp)
        forwarder = forwarding.ForwardHandler(hby=hby, mbx=self.mbx)
        exchanger = exchanging.Exchanger(hby=hby, handlers=[forwarder])
        rvy = routing.Revery(db=hby.db, cues=cues)

        clienter = Clienter()
        oobiery = Oobiery(hby=hby, clienter=clienter, rvy=rvy)

        rep = storing.Respondant(hby=hby, mbx=self.mbx, aids=self.aids)

        kvy = eventing.Kevery(db=hby.db, lax=True, local=False, rvy=rvy, cues=cues)
        kvy.registerReplyRoutes(router=rvy.rtr)

        tvy = Tevery(reger=verfer.reger, db=hby.db, local=False, cues=cues)

        tvy.registerReplyRoutes(router=rvy.rtr)
        self.parser = parsing.Parser(
            framed=True, kvy=kvy, tvy=tvy, exc=exchanger, rvy=rvy
        )

        witStart = indirecting.WitnessStart(
            hab=hab,
            parser=self.parser,
            cues=cues,
            kvy=kvy,
            tvy=tvy,
            rvy=rvy,
            exc=exchanger,
            replies=rep.reps,
            responses=rep.cues,
            queries=qrycues,
        )

        doers.extend([rep, witStart, *oobiery.doers])
        super(Witness, self).__init__(doers=doers, always=True)

    def enter(self, doers=None, *, temp=None):
        """Open the verifier registry before entering the doer loop.

        Parameters:
            doers (list | None): additional doers to enter alongside the witness doers.
            temp (bool | None): override the temp flag for this entry context.
        """
        if not self.reger.opened:
            self.reger.reopen()

        super(Witness, self).enter(doers=doers, temp=temp)

    def exit(self, deeds=None, **kwa):
        """Close all open resources on exit.

        Closes the keystore (``hby``), mailbox (``mbx``), and verifier registry
        (``reger``) in that order. Safe to call if any of these are already closed
        or None.
        """
        if self.hby:
            logger.info(f"Closing witness database {self.hby.name}")
            self.hby.close()

        if self.mbx:
            self.mbx.close()

        if self.reger:
            self.reger.close(clear=self.reger.temp)

    def oobis(self):
        """Return the list of OOBI URLs for this witness.

        Returns:
            list[str]: OOBI URLs in the form
            ``<scheme>://<host>:<port>/oobi/<pre>/controller``.
        """
        logger.info(f"{self.witery.url}/oobi/{self.hab.pre}/controller")
        oobis = [f"{self.witery.url}/oobi/{self.hab.pre}/controller"]
        return oobis

    def addCode(self, code):
        """Persist an encrypted TOTP code for this witness/controller pair.

        The code is keyed by ``(controller AID, witness AID)`` in the
        ``codes`` sub-database of :class:`~witopnet.core.basing.Baser`.

        Parameters:
            code (Cipher): encrypted TOTP secret to store.
        """
        cid = self.aids[0]
        self.witery.db.codes.pin(keys=(cid, self.hab.pre), val=code)

    def getCode(self):
        """Retrieve the encrypted TOTP code for this witness/controller pair.

        Returns:
            Cipher | None: the stored encrypted TOTP code, or ``None`` if not yet set.
        """
        cid = self.aids[0]
        return self.witery.db.codes.get(keys=(cid, self.hab.pre))


class WitnessCollectionEnd:
    """Boot API endpoint for provisioning new witnesses (``POST /witnesses``).

    Handles requests to create a new :class:`Witness` for a given controller AID
    and returns the witness endpoint identifier and OOBI URLs.
    """

    def __init__(self, witery: Witnessery):
        """
        Parameters:
            witery (Witnessery): registry of active witness instances.
        """
        self.witery = witery

    def on_post(self, req, rep):
        """Provision a new witness for the given controller AID.

        Parameters:
            req (Request): Falcon HTTP request. Body must be JSON with field
                ``aid`` containing the qb64 controller AID to be witnessed.
            rep (Response): Falcon HTTP response. Returns JSON with fields
                ``cid`` (controller AID), ``eid`` (witness AID), and
                ``oobis`` (list of OOBI URL strings).

        Raises:
            falcon.HTTPBadRequest: if ``aid`` is missing from the request body
                or is not a valid KERI prefix.
        """
        body = req.get_media()
        aid = httping.getRequiredParam(body, "aid")

        try:
            prefixer = coring.Prefixer(qb64=aid)
        except Exception as e:
            raise falcon.HTTPBadRequest(
                description=f"invalid AID for witnessing: {e.args[0]}"
            )

        try:
            witness = self.witery.createWitness(aid=aid)
        except kering.ConfigurationError as e:
            raise falcon.HTTPBadRequest(description=e.args[0])

        oobis = witness.oobis()

        data = dict(cid=prefixer.qb64, eid=witness.hab.pre, oobis=oobis)
        rep.status = falcon.HTTP_200
        rep.content_type = "application/json"
        rep.data = json.dumps(data).encode("utf-8")


class WitnessResourceEnd:
    """Boot API endpoint for managing individual witnesses (``DELETE /witnesses/{eid}``)."""

    def __init__(self, witery: Witnessery):
        """
        Parameters:
            witery (Witnessery): registry of active witness instances.
        """
        self.witery = witery

    def on_delete(self, _, rep, eid):
        """Delete a running witness. This operation is not reversible.

        Parameters:
            _ (Request): Falcon request object (unused).
            rep (Response): Falcon response object.
            eid (str): qb64 AID of the witness to delete.

        Raises:
            falcon.HTTPBadRequest: if ``eid`` is not a valid KERI prefix or
                witness deletion fails validation.
            falcon.HTTPNotFound: if ``eid`` does not correspond to a known
                witness.
        """
        try:
            coring.Prefixer(qb64=eid)
        except Exception as e:
            raise falcon.HTTPBadRequest(
                description=f"invalid AID for witnessing: {e.args[0]}"
            )

        try:
            self.witery.deleteWitness(eid=eid)
        except ValueError as e:
            raise falcon.HTTPNotFound(description=e.args[0])
        except kering.ConfigurationError as e:
            raise falcon.HTTPBadRequest(description=e.args[0])

        rep.status = falcon.HTTP_204
        rep.text = "Witness deleted."


class HealthEnd:
    """Liveness probe endpoint (``GET /health``).

    Returns ``204 No Content`` to indicate the service is alive. Intended for
    use by container orchestration health checks.
    """

    @staticmethod
    def on_get(_, resp):
        """Return 204 No Content to indicate the service is alive.

        Parameters:
            _ (Request): Falcon HTTP request (unused).
            resp (Response): Falcon HTTP response.
        """
        resp.status = falcon.HTTP_NO_CONTENT
