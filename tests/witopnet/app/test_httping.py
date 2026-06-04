# -*- encoding: utf-8 -*-

import falcon
import pytest
from keri import kering

from witopnet.core import httping


class FakeReq:
    def __init__(self, *, headers=None, params=None):
        self.headers = headers or {}
        self.params = params or {}

    def get_header(self, name):
        return self.headers.get(name)

    def get_param(self, name):
        return self.params.get(name)


def test_request_version_defaults_to_keri20():
    """Test that the default version is KERI 2.0 when no parameter is provided"""
    req = FakeReq()

    # Generated responses should be v2 unless the client explicitly opts into v1.
    assert httping.requestVersion(req) == kering.Vrsn_2_0


def test_request_version_accepts_query_param_when_header_missing():
    """Test that version can be specified"""
    req = FakeReq(params={"version": "1.0"})

    # GET-style callers can negotiate a legacy reply without sending a
    # CESR-VERSION header
    assert httping.requestVersion(req) == kering.Vrsn_1_0


def test_request_version_header_takes_precedence_over_query_param():
    """Test that the header takes precedence over the query parameter"""
    req = FakeReq(
        headers={"CESR-VERSION": "2.0"},
        params={"version": "1.0"},
    )

    # Keep one clear priority rule so explicit headers override bookmarked
    # or copied query-string values
    assert httping.requestVersion(req) == kering.Vrsn_2_0


@pytest.mark.parametrize("value", ["3.0", "garbage"])
def test_request_version_rejects_unsupported_versions(value):
    req = FakeReq(headers={httping.CESR_VERSION_HEADER: value})

    # The API contract is only v1/v2 compatible, so unknown versions should
    # fail loudly instead of silently falling back
    with pytest.raises(falcon.HTTPBadRequest):
        httping.requestVersion(req)
