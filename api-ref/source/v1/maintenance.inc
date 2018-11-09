.. -*- rst -*-

===========
Maintenance
===========

Create maintenance session
==========================

.. rest_method:: POST /v1/maintenance

Create a new maintenance session. You can specify a list of 'hosts' to be
maintained or have an empty list to indicate those should be self-discovered.
You need to have an initial state for the workflow in 'state'. 'workflow'
indicates the name of a Python plug-in to be used in the maintenance.

--Not yet implemented--

'download' can contain a list of URLs from where the needed software changes
are downloaded. It can also provide plug-ins to be used.

'actions' can contain a list of action plug-ins to be called before maintenance
starts, on each host or after the maintenance.

Request
-------

.. rest_parameters:: parameters.yaml

    - hosts: hosts

.. literalinclude:: samples/create-maintenance-session-post.json
   :language: javascript

Response codes
--------------

.. rest_status_code:: success status.yaml

    - 200

.. rest_status_code:: error status.yaml

    - 404

