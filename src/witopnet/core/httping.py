# -*- encoding: utf-8 -*-

"""
KERI
witopnet.core.httping package

"""

import falcon
from keri import kering
from keri.core import counting


CESR_VERSION_HEADER = "CESR-VERSION"
DEFAULT_PROTOCOL_VERSION = kering.Vrsn_2_0
SUPPORTED_PROTOCOL_VERSIONS = {
    "1": kering.Vrsn_1_0,
    "1.0": kering.Vrsn_1_0,
    "2": DEFAULT_PROTOCOL_VERSION,
    "2.0": DEFAULT_PROTOCOL_VERSION,
}


def getRequiredParam(body, name):
    """Extract a required parameter from a request body dict.

    Parameters:
        body (dict): parsed request body
        name (str): name of the required field

    Returns:
        object: the value of the field

    Raises:
        falcon.HTTPBadRequest: if the field is absent or None
    """
    param = body.get(name)
    if param is None:
        raise falcon.HTTPBadRequest(
            description=f"required field '{name}' missing from request"
        )

    return param


def requestVersion(req, default=DEFAULT_PROTOCOL_VERSION):
    """Resolve the requested outbound KERI protocol version from HTTP input.

    The version may be provided via the ``CESR-VERSION`` header or the
    ``version`` query parameter. When unspecified, ``default`` is returned.
    """
    value = req.get_header(CESR_VERSION_HEADER)
    if value is None:
        value = req.get_param("version")

    if value is None:
        return default

    text = value.strip()
    if text in SUPPORTED_PROTOCOL_VERSIONS:
        return SUPPORTED_PROTOCOL_VERSIONS[text]

    try:
        version = counting.Counter.b64ToVer(text)
    except ValueError as exc:
        raise falcon.HTTPBadRequest(
            description=(
                f"unsupported KERI protocol version '{value}', expected 1.0 or 2.0"
            )
        ) from exc

    if version in (kering.Vrsn_1_0, DEFAULT_PROTOCOL_VERSION):
        return version

    raise falcon.HTTPBadRequest(
        description=(
            f"unsupported KERI protocol version '{value}', expected 1.0 or 2.0"
        )
    )
