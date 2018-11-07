.. _admin:

=====
Admin
=====

These APIs are meant for infrastructure admin who is in charge of triggering
the rolling maintenance and upgrade workflows.

Create maintenance session
==========================

:POST: /v1/maintenance

Create a new maintenance session. You can specify a list of 'hosts' to be
maintained or have an empty list to indicate those should be self-discovered.
You need to have an initial state for the workflow in 'state'. 'workflow'
indicates the name of a Python plug-in to be used in the maintenance.

--Not yet implemented--

'download' can contain a list of URLs from where the needed software changes
are downloaded. It can also provide plug-ins to be used.

'actions' can contain a list of action plug-ins to be called during the workflow
plug-in execution. It is up to workflow plug-in implementation to support
different type of plug-ins or to decide how they are executed. Fenix default
workflow supported types and execution order is defined below.

Request
-------

+-------------------+----------------------+-----------------------------------------+-------------+-----------+
| Name              | Type                 | Description                             | Implemented | Mandatory |
+===================+======================+=========================================+=============+===========+
| hosts             | list of strings      | Unique name of the host                 | Yes         | Yes       |
+-------------------+----------------------+-----------------------------------------+-------------+-----------+
| state             | string               | Maintenance workflow state              | Yes         | Yes       |
+-------------------+----------------------+-----------------------------------------+-------------+-----------+
| maintenance_at    | time string          | Maintenance workflow start time         | Yes         | Yes       |
+-------------------+----------------------+-----------------------------------------+-------------+-----------+
| workflow          | string               | Maintenance workflow to be used         | Yes         | Yes       |
+-------------------+----------------------+-----------------------------------------+-------------+-----------+
| metadata          | dictionary           | Metadata; like hints to projects        | Yes         | Yes       |
+-------------------+----------------------+-----------------------------------------+-------------+-----------+
| download          | list of dictionaries | List of needed SW upgrades              | No          | No        |
+-------------------+----------------------+-----------------------------------------+-------------+-----------+
| download.url      | string               | URL to SW package                       | No          | No        |
+-------------------+----------------------+-----------------------------------------+-------------+-----------+
| download.size     | string               | File size                               | No          | No        |
+-------------------+----------------------+-----------------------------------------+-------------+-----------+
| actions           | list of dictionaries | List of action plug-ins                 | No          | Yes       |
+-------------------+----------------------+-----------------------------------------+-------------+-----------+
| actions.plugin    | string               | plug-in name. Default workflow executes | No          | Yes       |
|                   |                      | plug-ins in an alphabetical order       |             |           |
+-------------------+----------------------+-----------------------------------------+-------------+-----------+
| actions.type      | string               | Default workflow support types:         | No          | Yes       |
|                   |                      | 'pre', 'host' or 'post'                 |             |           |
+-------------------+----------------------+-----------------------------------------+-------------+-----------+
| actions.metadata  | dictionary           | Metadata; hints to plug-ins             | No          | Yes       |
+-------------------+----------------------+-----------------------------------------+-------------+-----------+

Example:

.. code-block:: json

    {
        "hosts": [],
        "state": "MAINTENANCE",
        "maintenance_at": "2018-02-28 06:06:03",
        "metadata": {"openstack_version": "Queens"},
        "workflow": "default",
        "download": [
            {"url": "https://my.sw.upgrades.com/SW1.tar.gz", "size": "200M"},
            {"url": "https://my.sw.upgrades.com/ESW1.tar.gz", "size": "1M"},
            {"url": "https://my.sw.upgrades.com/plugins1.tar.gz", "size": "1M"}],
        "actions": [
            {"plugin": "prepare", "type": "pre"},
            {"plugin": "esw_upgrade", "type": "host", "metadata": {"upgrade": "ESW1"}},
            {"plugin": "os_upgrade", "type": "host", "metadata": {"upgrade": "SW1"}},
            {"plugin": "finalize", "type": "post"}]
    }

Response
--------

Normal response codes: OK(200)

+------------+--------+-------------+
| Name       | Type   | Description |
+============+========+=============+
| session_id | string | UUID        |
+------------+--------+-------------+

Example:

.. code-block:: json

    {
        "session_id": "695030ee-1c4d-11e8-a9b0-0242ac110002"
    }


Update maintenance session
==========================

--Not yet implemented--

Update existing maintenance session. This can be used to continue a failed
session.

:PUT: /v1/maintenance/<session_id>


Get maintenance sessions
========================

Get all ongoing maintenance sessions.

:GET: /v1/maintenance

Response
--------

Normal response codes: OK(200)

+------------+--------+-------------+
| Name       | Type   | Description |
+============+========+=============+
| session_id | string | UUID        |
+------------+--------+-------------+

Example:

.. code-block:: json

    {
        "session_id": ["695030ee-1c4d-11e8-a9b0-0242ac110002"]
    }

Get maintenance session
=======================

Get a maintenance session state.

:GET: /v1/maintenance/<session_id>

Response
--------

Normal response codes: OK(200)

+----------------+-----------------+---------------------------------+
| Name           | Type            | Description                     |
+================+=================+=================================+
| state          | string          | Maintenance workflow state      |
+----------------+-----------------+---------------------------------+

.. code-block:: json

    {
        "state": "MAINTENANCE_DONE"
    }


Delete maintenance session
==========================

Delete a maintenance session. Usually called after the session is successfully
finished.

:DELETE: /v1/maintenance/<session_id>

Normal response codes: OK(200)


Future
======

On top of some expected changes mentioned above, it will also be handy to get
detailed information about the steps run already in the maintenance session.
This will be helpful when need to figure out any correcting actions to
successfully finish a failed session. There is ongoing work to have everything
kept in a database and that will be a key feature to enable these changes.
