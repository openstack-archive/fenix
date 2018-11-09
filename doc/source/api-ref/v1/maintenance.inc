.. -*- rst -*-

===========
Maintenance
===========

Create maintenance session
==========================

.. rest_method:: POST /v1/maintenance/

Create a new maintenance session. You can specify a list of 'hosts' to be
maintained or have an empty list to indicate those should be self-discovered.
You need to have an initial state for the workflow in 'state'. 'workflow'
indicates the name of a Python plug-in to be used in the maintenance.

Planned future functionality
----------------------------

'download' can contain a list of URLs from where the needed software changes
are downloaded. It can also provide plug-ins to be used.

'actions' can contain a list of action plug-ins to be called before maintenance
starts, on each host or after the maintenance.

Request
-------

.. rest_parameters:: parameters.yaml

    - hosts: hosts
    - state: workflow-state
    - maintenance_at: maintenance-workflow-start-time
    - workflow: workflow-name
    - metadata: metadata
    - download: upgrade-list
    - actions: action-plugins
    - actions.plugin: action-plugin-name
    - actions.type: action-plugin-type
    - actions.metadata: action-metadata

.. literalinclude:: samples/create-maintenance-session-post.json
   :language: javascript

Response codes
--------------

.. rest_status_code:: success status.yaml

    - 200: create-maintenance-session-post

.. rest_status_code:: error status.yaml

    - 404

Update maintenance session (planned future functionality)
=========================================================

.. rest_method:: POST /v1/maintenance/{session_id}/

Update existing maintenance session. This can be used to continue a failed
session.

Request
-------

.. rest_parameters:: parameters.yaml

    - session_id: session_id

Get maintenance sessions
========================

.. rest_method:: GET /v1/maintenance/

Get all ongoing maintenance sessions.

Response codes
--------------

.. rest_status_code:: success status.yaml

    - 200: get-maintenance-sessions-get

.. rest_status_code:: error status.yaml

    - 404

Get maintenance session
=======================

.. rest_method:: GET /v1/maintenance/{session_id}/

Get a maintenance session state.

Request
-------

.. rest_parameters:: parameters.yaml

    - session_id: session_id

Response codes
--------------

.. rest_status_code:: success status.yaml

    - 200: get-maintenance-session-get

.. rest_status_code:: error status.yaml

    - 404

Delete maintenance session
==========================

.. rest_method:: DELETE /v1/maintenance/{session_id}/

Delete a maintenance session. Usually called after the session is successfully
finished.


.. rest_status_code:: success status.yaml

    - 200

.. rest_status_code:: error status.yaml

    - 404

Future
======

On top of some expected changes mentioned above, it will also be handy to get
detailed information about the steps run already in the maintenance session.
This will be helpful when need to figure out any correcting actions to
successfully finish a failed session. There is ongoing work to have everything
kept in a database and that will be a key feature to enable these changes.
