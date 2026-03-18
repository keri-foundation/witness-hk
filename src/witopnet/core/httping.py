# -*- encoding: utf-8 -*-

"""
KERI
witopnet.core.httping package

"""

import falcon


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
