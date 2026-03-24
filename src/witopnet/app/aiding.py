# -*- encoding: utf-8 -*-
import json
from urllib.parse import urlparse

import falcon.errors
import pyotp
from falcon.media.multipart import MultipartParseError
from keri.kering import Schemes
from keri.app.httping import CESR_DESTINATION_HEADER
from keri.core import Encrypter, Matter, MtrDex
from keri.core.serdering import SerderKERI


def loadEnds(app, witery):
    """Register AID authentication endpoints on the Falcon application.

    Parameters:
        app (falcon.App): Falcon WSGI application to register routes on
        witery (Witnessery): registry of active witness instances
    """
    aidEnd = AidCollectionEnd(witery=witery)
    app.add_route("/aids", aidEnd)


class AidCollectionEnd:
    """AID authentication registration endpoint (POST /aids).

    Accepts a controller's KEL inception event along with an optional TOTP
    secret, verifies the inception event, encrypts a TOTP code with both the
    witness's and the controller's public keys, and returns the encrypted code
    and the witness OOBI URL to the caller.
    """

    def __init__(self, witery):
        """
        Parameters:
            witery (Witnessery): registry of active witness instances
        """
        self.witery = witery

    def on_post(self, req, rep):
        """Register a controller AID with this witness using TOTP 2FA.

        Expects a ``multipart/form-data`` body with the following parts:
            - ``kel`` (required): CESR stream of the controller's inception event
            - ``delkel`` (optional): CESR stream of a delegator's KEL, required for
              delegated AIDs
            - ``secret`` (optional): caller-supplied TOTP seed; a random one is
              generated if omitted

        On success, returns JSON with:
            - ``totp``: the TOTP code encrypted with the *controller's* public key
            - ``oobi``: the witness OOBI URL the controller should resolve

        Parameters:
            req (Request): Falcon HTTP request object
            rep (Response): Falcon HTTP response object

        Raises:
            falcon.HTTPBadRequest: if the CESR destination header is missing,
                the AID is unrecognized, the KEL is invalid, or the key type
                is unsupported
            falcon.HTTPUnsupportedMediaType: if the content type is not
                ``multipart/form-data``
        """
        if CESR_DESTINATION_HEADER not in req.headers:
            raise falcon.HTTPBadRequest(title="CESR request destination header missing")

        aid = req.headers[CESR_DESTINATION_HEADER]

        witness = self.witery.lookup(aid)
        if witness is None:
            raise falcon.HTTPBadRequest(description=f"AID {aid} is not recognized")

        if not req.content_type.startswith("multipart/form-data"):
            raise falcon.HTTPUnsupportedMediaType(
                description=f"{req.content_type} not accepted, must be multipart/form-data"
            )

        form = req.get_media()
        kel = None
        delkel = None
        secret = None
        try:
            for part in form:
                if part.name == "kel":
                    # We are expecting a CESR stream of an inception event
                    kel = part.stream.read()

                elif part.name == "delkel":
                    # We are expecting a CESR stream of a KEL event
                    delkel = part.stream.read()

                elif part.name == "secret":
                    # Optionally, an otp secret is included with the request for batch authentication
                    secret = part.stream.read()

        except (
            MultipartParseError
        ):  # The form works but still raises this exception so ignore for now...
            pass

        # A delkel will be provided if the target KEL is a delegated AID
        if delkel is not None:
            witness.parser.parse(delkel, local=False)

        serder = SerderKERI(raw=bytes(kel))
        # Parse the event, get the KEL in our Kevers
        witness.parser.parse(kel, local=False)

        if serder.pre not in witness.hab.kevers:  # Not a valid, signed inception event
            raise falcon.HTTPBadRequest(
                description="KEL part not valid inception event"
            )

        if serder.pre not in witness.aids:
            raise falcon.HTTPBadRequest(
                description=f"{serder.pre} is not valid for this witness"
            )

        # Create the time based OTP for use when receipting
        code = pyotp.random_base32().encode("utf-8")

        if secret is not None:
            code = secret

        # Create a Ciper from our own Hab to save the code encrypted
        verfer = witness.hab.kever.verfers[0]
        if verfer.code not in (MtrDex.Ed25519N, MtrDex.Ed25519):
            raise ValueError(
                "Unsupported verkey derivation code = {}." "".format(verfer.code)
            )
        encrypter = Encrypter(verkey=verfer.qb64b)

        seedqb64b = Matter(raw=code, code=MtrDex.Ed25519_Seed).qb64b
        cipher = encrypter.encrypt(ser=seedqb64b)
        witness.addCode(code=cipher)

        # Now generate the encrypted code to send to the originator of the call
        kever = witness.hab.kevers[serder.pre]

        verfer = kever.verfers[0]
        if verfer.code not in (MtrDex.Ed25519N, MtrDex.Ed25519):
            raise ValueError(
                "Unsupported verkey derivation code = {}." "".format(verfer.code)
            )

        encrypter = Encrypter(verkey=verfer.qb64b)
        seedqb64b = Matter(raw=code, code=MtrDex.Ed25519_Seed).qb64b
        cipher = encrypter.encrypt(ser=seedqb64b)

        urls = witness.hab.fetchUrls(
            eid=witness.hab.pre, scheme=Schemes.http
        ) or witness.hab.fetchUrls(eid=witness.hab.pre, scheme=Schemes.https)
        if not urls:
            raise falcon.HTTPBadRequest(
                description=f"{witness.hab.name} identifier {witness.hab.pre} does not have any controller endpoints"
            )

        url = (
            urls[Schemes.http]
            if Schemes.http in urls
            else urls[Schemes.https]
        )
        up = urlparse(url)
        oobi = (
            f"{up.scheme}://{up.hostname}:{up.port}/oobi/{witness.hab.pre}/controller"
        )

        body = dict(totp=cipher.qb64, oobi=oobi)

        rep.content_type = "application/json"
        rep.status = falcon.HTTP_200
        rep.data = json.dumps(body).encode("utf-8")
