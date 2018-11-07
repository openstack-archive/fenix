.. _project:

=======
Project
=======

These APIs are meant for projects having instances on top of the infrastructure
under corresponding rolling maintenance or upgrade session. Usage of these APIs
expects there is an application manager (VNFM) that can interact with Fenix
workflow via these APIs. If this is not the case, workflow should have a default
behavior for instances owned by projects, that are not interacting with Fenix.

These APIs are generic for any cloud as instance ID should be something that can
be matched to virtual machines or containers regardless of the cloud underneath.

Get project maintenance session
===============================

Get project instances belonging to the current state of maintenance session.
the Project-manager receives an AODH event alarm telling about different
maintenance states. Event data field length is very limited, so instances cannot
be given as a list in the event. Instead, there will be an URL given to below
API to get a project-specific list of instances.

:GET /v1/maintenance/<session_id>/<projet_id>/

Response
--------

Normal response codes: OK(200)

+--------------+-----------------+----------------------+
| Name         | Type            | Description          |
+==============+=================+======================+
| instance_ids | list of strings | List of instance IDs |
+--------------+-----------------+----------------------+

Example:

.. code-block:: json

    {
        "instance_ids": ["109e14d9-6566-42b3-93e4-76605f264d8f",
                         "71285107-f0fc-4428-a8b2-0b3edd64bcad"]
    }


Input from project to maintenance session
=========================================

Project having instances on top of the infrastructure handled by a maintenance
session might need to make own action for its instances on top of a host going
into maintenance next, or reply an admin action to be done. This is, as the host
can go down or even be removed and the instances should be then running safely
somewhere else. Project manager receives an AODH event alarm telling which
instances are affected and when the project is ready, it makes its own action or
replies back an action which needs the admin privileges.

:PUT /v1/maintenance/<session_id>/<projet_id>/

Request
-------

+------------------+------------+-------------------------------------------------+
| Name             | Type       | Description                                     |
+==================+============+=================================================+
| instance_actions | dictionary | instance ID : action string                     |
+------------------+------------+-------------------------------------------------+
| state            | string     | There can have different values depending on    |
|                  |            | what is the maintenance session state to reply  |
|                  |            | to. In the below example, the maintenance state |
|                  |            | is 'PLANNED_MAINTENANCE' and the reply state is |
|                  |            | formed by adding 'ACK\_' or 'NACK\_' as the     |
|                  |            | prefix to reply value                           |
+------------------+------------+-------------------------------------------------+

Example:

.. code-block:: json

    {
        "instance_actions": {"109e14d9-6566-42b3-93e4-76605f264d8f": "MIGRATE",
                             "71285107-f0fc-4428-a8b2-0b3edd64bcad": "MIGRATE"},
        "state": "ACK_PLANNED_MAINTENANCE"
    }

Response
--------

Normal response codes: OK(200)
