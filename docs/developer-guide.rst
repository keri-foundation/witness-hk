Developer Guide
===============

Environment
-----------

The current package metadata allows Python ``>=3.12.6``, but the team has already seen
local issues on Python ``3.14``. Until that runtime is verified, use Python ``3.13`` for
local development and documentation work.

Setup
-----

From the repository root:

.. code-block:: bash

   python3.13 -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   python -m pip install -e .

Architecture
------------

Witopnet runs two HTTP servers side by side:

- **Boot server** (default ``127.0.0.1:5631``): management API. Use this to provision
  new witnesses (``POST /witnesses``), delete witnesses (``DELETE /witnesses/{eid}``),
  and check liveness (``GET /health``).

- **Witness server** (default ``127.0.0.1:5632``): KERI event processing. Handles
  event ingestion (``POST /``), receipting (``POST /receipts``), AID authentication
  registration (``POST /aids``), OOBI resolution (``GET /oobi/...``), key-state
  queries (``GET /ksn``), and KEL replay (``GET /log``).

Each provisioned witness gets its own non-transferable KERI identifier (Hab), its own
keystore, and its own mailbox. The ``Witnessery`` class manages all running witnesses
and persists their records in an LMDB database via ``Baser``.

Quick Start
-----------

Start the witness service with default ports:

.. code-block:: bash

   witopnet start

Or specify ports explicitly:

.. code-block:: bash

   witopnet start --http 5632 --bootport 5631

To provision a witness for a controller AID, send a request to the boot server:

.. code-block:: bash

   curl -X POST http://127.0.0.1:5631/witnesses \
        -H "Content-Type: application/json" \
        -d '{"aid": "<qb64-controller-aid>"}'

The response will contain the witness AID (``eid``) and OOBI URLs the controller
should resolve.

Building the Docs
-----------------

From the repository root:

.. code-block:: bash

   pip install -e .
   pip install sphinx sphinx-rtd-theme
   cd docs
   sphinx-build -b html . _build/html

To do a clean rebuild:

.. code-block:: bash

   rm -rf _build
   sphinx-build -b html . _build/html