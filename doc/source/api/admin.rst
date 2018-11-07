.. _admin:

=====
Admin
=====

Definition of admin API

Create maintenance session
==========================

:POST: /v1/maintenance

Create a new maintenance session. You can specify a list of 'hosts' to be
maintained or have an empty list to indicate those should be self-discovered.
You need to have an initial state for the workflow in 'state'. 'workflow'
indicates the name of a Python plug-in to be used in the maintenance.

--Not yet implemented--

In 'download' there can be a list of URLs from where the needed software
changes are downloaded. It can also provide plug-ins to be used.

'actions' will list the action plug-ins to be used before maintenance starts,
on each host or after the maintenance.

Request
-------

+----------------+-----------------+---------------------------------+
| Name           | Type            | Description                     |
+================+=================+=================================+
| hosts          | list of strings | Unique name of the host         |
+----------------+-----------------+---------------------------------+
| state          | string          | Maintenance workflow state      |
+----------------+-----------------+---------------------------------+
| maintenance_at | time string     | Maintenance workflow statr time |
+----------------+-----------------+---------------------------------+
| workflow       | string          | Maintenance workflow to be used |
+----------------+-----------------+---------------------------------+

--Not yet implemented--

+----------------+----------------------+----------------------------+
| Name           | Type                 | Description                |
+================+======================+============================+
| download       | list of dictionaries | List of needed SW upgrades |
+----------------+----------------------+----------------------------+
| url            | string               | URL to SW package          |
+----------------+----------------------+----------------------------+
| size           | string               | File size                  |
+----------------+----------------------+----------------------------+

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
            {"order": 1, "plugin": "prepare", "type": "pre"},
            {"order": 1, "plugin": "esw_upgrade", "type": "host", "metadata": {"upgrade": "ESW1"}},
            {"order": 2, "plugin": "os_upgrade", "type": "host", "metadata": {"upgrade": "SW1"}},
            {"order": 1, "plugin": "finalize", "type": "post"}]
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
