Developer Guide
===============

Witopnet is a `KERI <https://github.com/WebOfTrust/keri>`_ witness service that provides
authenticated event receipting for KERI identifiers. Witnesses are provisioned dynamically
via a management API and secured with TOTP-based two-factor authentication before receipting
events.

Environment
-----------

Witopnet requires Python ``3.14`` or newer. ``pyproject.toml`` declares
``requires-python = ">=3.14.0"``.

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

   python3.14 -m venv .venv
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

   mkdir -p /tmp/witness-demo/keri/cf/main

   cat > /tmp/witness-demo/keri/cf/main/witopnet.json <<'EOF'
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
   ``keri/``), not into ``keri/`` itself. KERI appends ``keri/cf/`` *and* a
   ``main`` segment internally, so the file it reads is
   ``<config-dir>/keri/cf/main/witopnet.json``.

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

You should see a log line confirming both servers started (the boot server is
the "internal" one):

.. code-block:: text

   ******* Starting Witness Operational Network listening internally: http/5631, externally: http/5632 .******

Step 3: Verify liveness
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   curl -i http://127.0.0.1:5631/health

Expected: ``HTTP/1.1 204 No Content``

Step 4: Create a controller AID
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use ``kli`` (from keripy) to create a controller identifier:

.. code-block:: bash

   kli init --name controller --salt 0ACDEyMzQ1Njc4OWxtbZctrl --nopasscode
   kli incept --name controller --alias controller --file scripts/data/controller.json

.. note::

   The ``init`` and ``incept`` commands require ``kli`` to be installed
   (``pip install keri``). The salt above is a valid 24-character qb64 salt kept
   for local demonstration only; use a unique value in production. Short or
   malformed salts are rejected by ``kli init``.

   ``scripts/data/controller.json`` incepts the controller with no witnesses
   (``"wits": []``), so the witness is added later by rotation in Step 8.

Step 5: Provision the witness for your controller
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Get your controller AID:

.. code-block:: bash

   kli status --name controller --alias controller

Then provision the witness:

.. code-block:: bash

   curl -s -X POST http://127.0.0.1:5631/witnesses \
     -H "Content-Type: application/json" \
     -d '{"aid": "<your-controller-aid>"}'

The response contains the witness AID and its OOBI URL:

.. code-block:: json

   {
     "cid": "<your-controller-aid>",
     "eid": "<witness-aid>",
     "oobis": ["http://127.0.0.1:5632/oobi/<witness-aid>/controller"]
   }

.. note::

   ``eid`` is the *witness* AID. The OOBI URL introduces the witness, so the AID
   in the path is the witness AID, not your controller AID. Use the ``oobis[0]``
   value verbatim in the next step.

Step 6: Resolve the OOBI
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   kli oobi resolve --name controller --oobi-alias witness0 \
     --oobi "http://127.0.0.1:5632/oobi/<witness-aid>/controller"

Substitute the ``oobis[0]`` URL returned in Step 5. Resolving the OOBI teaches
the controller the witness's endpoint and verifies the witness identifier.
``scripts/controller.sh`` performs the same call, extracting the URL with
``jq -r .oobis[0]``.

Step 7: Authenticate with TOTP
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Before the witness will receipt events, the controller must register its AID
with two-factor authentication:

.. code-block:: bash

   kli witness authenticate --name controller --alias controller \
     --witness "<witness-aid>"

This is the CLI form of the ``POST /aids`` call in the :ref:`api-reference`: it
sends the controller's KEL as ``multipart/form-data`` with a
``CESR-Destination`` header naming the witness, and receives a TOTP-encrypted
code in return. ``--witness`` accepts either the witness AID or the
``--oobi-alias`` used in Step 6.

The witness must already be provisioning this controller (Step 5); it rejects
AIDs it does not recognize.

Step 8: Submit events for receipting
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Once the controller is authenticated, add the witness to the identifier and
request receipts:

.. code-block:: bash

   kli rotate --name controller --alias controller \
     --witness-add "<witness-aid>" \
     --receipt-endpoint --authenticate

``--receipt-endpoint`` requests receipts from the witness receipt endpoint
(``POST /receipts``) and ``--authenticate`` supplies the TOTP code from Step 7.

.. note::

   The controller was incepted with no witnesses, so this rotation is what adds
   the witness. The first event the witness can receipt is therefore this
   rotation, at sequence number ``1``, not the inception at ``0``.

To re-submit the controller's current event to its witnesses, use
``witopnet marshal submit`` (see Submitting Events below).

Step 9: Verify receipting
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   curl -i "http://127.0.0.1:5632/receipts?pre=<controller-aid>&sn=1" \
     -H "CESR-Destination: <witness-aid>"

A ``200`` response carries the receipt as a CESR stream. The header and query
parameters all matter here:

- ``CESR-Destination`` is required and must name the witness AID; without it the
  request is rejected with ``400``.
- ``pre`` is the controller AID.
- ``sn`` must name an event at which this witness is one of the controller's
  witnesses, which is why ``1`` (the Step 8 rotation) is used rather than ``0``.
- Pass ``said`` instead of ``sn`` to look up a receipt by event SAID.

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
``scripts/keri/cf/main/witopnet.json``:

.. code-block:: json

   {
     "dt": "2022-01-20T12:57:59.823350+00:00",
     "witopnet": {
       "dt": "2022-01-20T12:57:59.823350+00:00",
       "curls": ["http://127.0.0.1:5632/"]
     }
   }

``witopnet.curls[0]`` sets the URL the witness advertises in its OOBI and endpoint
records, overriding ``--host``, ``--http``, and the scheme. It does not change the
address the servers bind to; that comes from ``--host`` and ``--http``.

Pass the directory one level *above* ``keri/`` to ``--config-dir``. KERI appends
``keri/cf/`` and a ``main`` segment internally, so the file read is
``<config-dir>/keri/cf/main/witopnet.json``. Note that ``kli`` appends only
``keri/cf/`` when given ``--config-file``, so its config files sit one level
higher than the witness config file.

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
     - Directory one level above ``keri/``. The file read is
       ``<config-dir>/keri/cf/main/witopnet.json``
   * - ``--loglevel``
     - ``INFO``
     - Log level: ``DEBUG``, ``INFO``, ``WARNING``, ``ERROR``, ``CRITICAL``
   * - ``--logfile``
     - —
     - Path to write log output to file

``--config-file`` is accepted by the CLI but is not currently passed through to
the witness setup, so it has no effect. Select the config file with
``--config-dir``.

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
     --name controller \
     --alias controller

``--passcode`` is the *keystore* passcode, not a witness code; omit it for a
keystore created with ``kli init --nopasscode``. Submission only happens when the
current event already names witnesses, so add a witness first (Step 8). Add
``--force`` to re-send receipts even when a full complement already exists.

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
     - Submit a KERI event (KEL/EXN/TEL/QRY) with CESR attachments. Requires
       ``CESR-Destination: <witness-aid>``; an optional ``Authorization`` TOTP
       header controls whether the event is parsed as locally authenticated
   * - ``PUT``
     - ``/``
     - Push raw CESR bytes into the inbound stream
   * - ``POST``
     - ``/aids``
     - Register a controller AID with 2FA. Requires
       ``CESR-Destination: <witness-aid>``. Body: ``multipart/form-data`` with
       ``kel``, optional ``delkel``, optional ``secret``
   * - ``POST``
     - ``/receipts``
     - Request a witness receipt. Requires ``CESR-Destination: <witness-aid>`` and
       an ``Authorization`` header with TOTP
   * - ``GET``
     - ``/receipts``
     - Retrieve a stored receipt. Requires ``CESR-Destination: <witness-aid>``;
       query params ``pre`` and ``sn`` or ``said``
   * - ``GET``
     - ``/ksn``
     - Get the key state notice for a prefix. Requires
       ``CESR-Destination: <witness-aid>``; query param ``pre``
   * - ``GET``
     - ``/log``
     - Replay KEL events for a prefix. Requires ``CESR-Destination: <witness-aid>``;
       query param ``pre``, optional ``fn``, ``s``, and ``a``
   * - ``GET``
     - ``/oobi/{aid}``
     - OOBI resolution endpoint
   * - ``GET``
     - ``/oobi/{aid}/{role}``
     - OOBI with role
   * - ``GET``
     - ``/oobi/{aid}/{role}/{eid}``
     - OOBI with role and participant EID

Witness-server endpoints identify which witness the request is for with the
``CESR-Destination`` header. The value must name a witness AID this service is
currently running; an unknown AID is rejected with ``400``.

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
    Ensure ``--config-dir`` points one level *above* ``keri/``, not inside it.
    KERI looks for ``<config-dir>/keri/cf/main/witopnet.json``.

**Port already in use**
    Change ``--http`` or ``--bootport``. Both servers must bind to unique ports.
    Find the process holding the port with ``lsof -nP -iTCP:5632 -sTCP:LISTEN``
    and stop that process, or stop the running service with Ctrl-C.

**"AID ... is not recognized" when authenticating**
    The witness only authenticates controllers it is currently provisioning.
    Provision the witness (Step 5) before running ``kli witness authenticate``.

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
   sphinx-build -b dirhtml . _build/html

Next: Watcher
-------------

This witness service is paired with ``watopnet`` (``watcher-hk``), a KERI
watcher that monitors AIDs and verifies key-event consistency across witnesses.
See the `watcher-hk repository <https://github.com/keri-foundation/watcher-hk>`_
for its developer guide.
