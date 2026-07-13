Developer Guide
===============

Witopnet is a `KERI <https://github.com/WebOfTrust/keri>`_ witness service that provides
authenticated event receipting for KERI identifiers. Witnesses are provisioned dynamically
via a management API and secured with TOTP-based two-factor authentication before receipting
events.

Environment
-----------

The current package metadata requires Python ``>=3.12.6`` (``>=3.14.0`` on main).
Use Python ``3.14`` for development and documentation work — this matches the
Read the Docs build configuration.

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

End-to-End Walkthrough
----------------------

This section walks through the complete flow: starting a witness, provisioning
it for a controller, and verifying it receipts events. Follow these steps in
order. If you get stuck, see the :ref:`troubleshooting` section.

Step 1: Prepare the config directory
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Create a config directory with the KERI config file structure:

.. code-block:: bash

   mkdir -p /tmp/witness-demo/keri/cf

   cat > /tmp/witness-demo/keri/cf/witopnet.json <<'EOF'
   {
     "dt": "2024-01-01T00:00:00.000000+00:00",
     "witopnet": {
       "dt": "2024-01-01T00:00:00.000000+00:00",
       "curls": ["http://127.0.0.1:5632/"]
     }
   }
   EOF

.. note::

   ``--config-dir`` must point to ``/tmp/witness-demo`` (one level *above*
   ``keri/``), not to ``/tmp/witness-demo/keri/cf/``. KERI appends
   ``keri/cf/`` internally and looks for ``witopnet.json`` there.

Step 2: Start the witness
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   witopnet marshal start \
     --config-dir /tmp/witness-demo \
     --base witopnet \
     --host 127.0.0.1 \
     --http 5632 \
     --boothost 127.0.0.1 \
     --bootport 5631

You should see log output confirming both servers started:

.. code-block:: text

   Starting Witness Operational Network
   listening internally: http/5631, externally: http/5632

Step 3: Verify liveness
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   curl -i http://127.0.0.1:5631/health

Expected: ``HTTP/1.1 204 No Content``

Step 4: Create a controller AID
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use ``kli`` (from keripy) to create a controller identifier:

.. code-block:: bash

   kli init --name controller --salt 0AControllerSalt00 --nopasscode
   kli incept --name controller --alias controller --file /tmp/witness-demo/keri/cf/witopnet.json

.. note::

   The ``init`` and ``incept`` commands require ``kli`` to be installed
   (``pip install keri``). The salt here is for demonstration only — use
   a unique value in production.

Step 5: Provision the witness for your controller
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Get your controller AID:

.. code-block:: bash

   kli status --name controller --alias controller

Then provision the witness:

.. code-block:: bash

   curl -X POST http://127.0.0.1:5631/witnesses \
     -H "Content-Type: application/json" \
     -d '{"aid": "<your-controller-aid>"}'

The response includes ``oobis`` URLs. Copy the OOBI URL for the next step.

Step 6: Resolve the OOBI
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   curl http://127.0.0.1:5632/oobi/<your-controller-aid>/controller

This returns a CESR stream containing the witness's key event log. The
controller uses this to discover the witness's endpoint and verify its
identifier.

Step 7: Authenticate with TOTP
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Before the witness will receipt events, the controller must register its AID
with two-factor authentication. See the ``POST /aids`` endpoint in the
:ref:`api-reference`.

Step 8: Submit events for receipting
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Once the controller is authenticated, use ``marshal submit`` to submit events:

.. code-block:: bash

   witopnet marshal submit \
     --name controller \
     --alias controller \
     --passcode <your-passcode>

The witness will receipt each event and store the receipt for later retrieval.

Step 9: Verify receipting
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   curl "http://127.0.0.1:5632/receipts?pre=<controller-aid>&sn=0"

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

.. _api-reference:

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

.. _troubleshooting:

Troubleshooting
---------------

**"No such file or directory" when starting**
    Ensure ``--config-dir`` points one level *above* ``keri/``, not inside
    ``keri/cf/``. KERI looks for ``<config-dir>/keri/cf/witopnet.json``.

**Port already in use**
    Change ``--http`` or ``--bootport``. Both servers must bind to unique
    ports. Kill any existing ``witopnet`` processes first:
    ``pkill -f witopnet``.

**"Unknown sender key state" on provision**
    The controller AID must be incepted before provisioning. Run ``kli incept``
    first — see Step 4 in the End-to-End Walkthrough above.

**ImportError: libsodium not found**
    Install libsodium: ``brew install libsodium`` (macOS) or
    ``sudo apt-get install libsodium-dev`` (Ubuntu/Debian).

**ModuleNotFoundError: No module named 'witopnet'**
    Install the package in development mode: ``pip install -e .`` from the
    repository root.

Building the Docs
-----------------

From the repository root:

.. code-block:: bash

   pip install -e .
   pip install sphinx sphinx-rtd-theme
   cd docs
   sphinx-build -b dirhtml . _build/html

To do a clean rebuild:

.. code-block:: bash

   rm -rf _build

Next: Watcher
-------------

This witness service is paired with ``watopnet`` (``watcher-hk``), a KERI
watcher that monitors AIDs and verifies key-event consistency across witnesses.
See the `watcher-hk repository <https://github.com/keri-foundation/watcher-hk>`_
for its developer guide.
   sphinx-build -b html . _build/html