# -*- encoding: utf-8 -*-

import pytest
import random
import io


@pytest.fixture
def multipart():
    return Multipart


class Multipart:
    @staticmethod
    def create(fargs, content_type="text/plain; charset=utf-8"):
        """
        Basic emulation of a browser's multipart file upload
        """
        boundary = "____________{0:012x}".format(
            random.randint(123456789, 0xFFFFFFFFFFFF)
        )
        buff = io.BytesIO()
        for fieldname, data in fargs.items():
            buff.write(b"--")
            buff.write(boundary.encode())
            buff.write(b"\r\n")
            buff.write(f'Content-Disposition: form-data; name="{fieldname}"'.encode())
            buff.write(b"\r\n")
            buff.write(f"Content-Type: {content_type}".encode())
            buff.write(b"\r\n")
            buff.write(b"\r\n")
            buff.write(data)
            buff.write(b"\r\n--")
            buff.write(boundary.encode())
            buff.write(b"--\r\n")

        headers = {
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Content-Length": str(buff.tell()),
        }
        return buff.getvalue(), headers
