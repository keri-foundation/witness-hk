Developer Guide
===============

Witopnet is a `KERI <https://github.com/WebOfTrust/keri>`_ witness service that provides
authenticated event receipting for KERI identifiers. Witnesses are provisioned dynamically
via a management API and secured with TOTP-based two-factor authentication before receipting
events.

Environment
-----------

The current package metadata allows Python ``>=3.12.6``, but the team has already seen
local issues on Python ``3.14``. Until that runtime is verified, use Python ``3.13`` for
local development and documentation work.

Witopnet also requires ``libsodium``, which is a dependency of the ``keri`` package.

**macOS:**

.. code-block:: bash

   brew install libsodium

**Ubuntu/Debian:**

.. code-block:: bash

   sudo apt-get install libsodium-dev

Setup
-----

From the repository root:

.. code-block:: bash

   python3.13 -m venv .venv
   source .venv/bin/activate
   python -m pip install --upgrade pip
   python -m pip install -e .

For development with test dependencies:

.. code-block:: bash

   python -m pip install -e ".[dev]"

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
keystore, and its own mailbox. The :class:`~witopnet.core.witnessing.Witnessery` class
manages all running witnesses and persists their records in an LMDB database via
:class:`~witopnet.core.basing.Baser`.

Configuration
-------------

The witness server is configured via a KERI config file. A sample is provided at
``scripts/keri/cf/witopnet.json``:

.. code-block:: json

   {
     "dt": "2022-01-20T12:57:59.823350+00:00",
     "witopnet": {
       "dt": "2022-01-20T12:57:59.823350+00:00",
       "curls": ["http://127.0.0.1:5632/"]
     }
   }

The ``curls`` field sets the controller URL(s) advertised by the witness. Pass the
directory containing ``keri/cf/witopnet.json`` to ``--config-dir`` — KERI appends
``keri/cf/`` internally, so ``--config-dir`` must point one level *above* ``keri/``.

Running the Witness
-------------------

After installation, the ``witopnet`` CLI is available:

.. code-block:: bash

   witopnet marshal start \
     --config-dir /path/to/scripts \
     --base witopnet \
     --host 0.0.0.0 \
     --http 5632 \
     --boothost 127.0.0.1 \
     --bootport 5631

Key flags:

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Flag
     - Default
     - Description
   * - ``--host`` / ``-o``
     - ``127.0.0.1``
     - Host the witness server listens on
   * - ``--http`` / ``-H``
     - ``5632``
     - Port the witness server listens on
   * - ``--boothost`` / ``-bh``
     - ``127.0.0.1``
     - Host the boot server listens on
   * - ``--bootport`` / ``-bp``
     - ``5631``
     - Port the boot server listens on
   * - ``--base`` / ``-b``
     - ``""``
     - Path prefix for the KERI keystore (must be relative, not absolute)
   * - ``--config-dir`` / ``-c``
     - —
     - Directory one level above ``keri/cf/`` containing the config file
   * - ``--config-file``
     - —
     - Config filename override
   * - ``--loglevel``
     - ``INFO``
     - Log level: ``DEBUG``, ``INFO``, ``WARNING``, ``ERROR``, ``CRITICAL``
   * - ``--logfile``
     - —
     - Path to write log output to file

Set ``DEBUG_WITOPNET=1`` in your environment to print full tracebacks on errors.

To verify the service is running, hit the health endpoint:

.. code-block:: bash

   curl http://127.0.0.1:5631/health

A ``204 No Content`` response confirms the boot server is alive.

Provisioning a Witness
----------------------

To provision a new witness for a controller AID, send a request to the boot server:

.. code-block:: bash

   curl -X POST http://127.0.0.1:5631/witnesses \
        -H "Content-Type: application/json" \
        -d '{"aid": "<qb64-controller-aid>"}'

The response contains:

- ``cid``: the controller AID
- ``eid``: the witness AID
- ``oobis``: list of OOBI URLs the controller should resolve

Submitting Events
-----------------

The ``marshal submit`` subcommand submits a controller's current event to its witnesses
for receipting:

.. code-block:: bash

   witopnet marshal submit \
     --name <keystore-name> \
     --alias <identifier-alias> \
     --passcode <passcode>

HTTP API Reference
------------------

Boot server (``localhost:5631``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 10 30 60

   * - Method
     - Path
     - Description
   * - ``POST``
     - ``/witnesses``
     - Provision a new witness. Body: ``{"aid": "<qb64-AID>"}``
   * - ``DELETE``
     - ``/witnesses/{eid}``
     - Delete a witness by its endpoint identifier
   * - ``GET``
     - ``/health``
     - Liveness probe, returns ``204 No Content``

Witness server (``localhost:5632``)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 10 30 60

   * - Method
     - Path
     - Description
   * - ``POST``
     - ``/``
     - Submit a KERI event (KEL/EXN/TEL/QRY) with CESR attachments
   * - ``PUT``
     - ``/``
     - Push raw CESR bytes into the inbound stream
   * - ``POST``
     - ``/aids``
     - Register a controller AID with 2FA. Body: ``multipart/form-data`` with ``kel``, optional ``delkel``, optional ``secret``
   * - ``POST``
     - ``/receipts``
     - Request a witness receipt. Requires ``Authorization`` header with TOTP
   * - ``GET``
     - ``/receipts``
     - Retrieve a stored receipt by ``pre`` and ``sn`` or ``said``
   * - ``GET``
     - ``/ksn``
     - Get the key state notice for a prefix
   * - ``GET``
     - ``/log``
     - Replay KEL events for a prefix
   * - ``GET``
     - ``/oobi/{aid}``
     - OOBI resolution endpoint
   * - ``GET``
     - ``/oobi/{aid}/{role}``
     - OOBI with role
   * - ``GET``
     - ``/oobi/{aid}/{role}/{eid}``
     - OOBI with role and participant EID

Testing
-------

.. code-block:: bash

   pip install -e ".[dev]"
   pytest tests/

Tests are located under ``tests/witopnet/app/`` and cover the aiding, indirecting, and
witnessing modules. The test suite uses temporary in-memory KERI keystores so no external
services are required.

To run a specific test file:

.. code-block:: bash

   pytest tests/witopnet/app/test_witnessing.py -v

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