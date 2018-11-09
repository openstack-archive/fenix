.. -*- rst -*-

=======
Project
=======

These APIs are generic for any cloud as instance ID should be something that can
be matched to virtual machines or containers regardless of the cloud underneath.

Get project maintenance session
===============================

.. rest_method:: POST /v1/maintenance/{session_id}/{project_id}/

Get project instances belonging to the current state of maintenance session.
the Project-manager receives an AODH event alarm telling about different
maintenance states. Event data field length is very limited, so instances cannot
be given as a list in the event. Instead, there will be an URL given to below
API to get a project-specific list of instances.

Request
-------

.. rest_parameters:: parameters.yaml

    - session_id: uuid-path
    - project_id: uuid-path

Response codes
--------------

.. rest_status_code:: success status.yaml

    - 200: get-project-maintenance-session-post

.. rest_status_code:: error status.yaml

    - 404

Input from project to maintenance session
=========================================

.. rest_method:: PUT /v1/maintenance/{session_id}/{project_id}/

Project having instances on top of the infrastructure handled by a maintenance
session might need to make own action for its instances on top of a host going
into maintenance next, or reply an admin action to be done. This is, as the host
can go down or even be removed and the instances should be then running safely
somewhere else. Project manager receives an AODH event alarm telling which
instances are affected and when the project is ready, it makes its own action or
replies back an action which needs the admin privileges.

Request
-------

.. rest_parameters:: parameters.yaml

    - session_id: uuid-path
    - project_id: uuid-path
    - instance_actions: instance-actions
    - state: workflow-state-reply

.. literalinclude:: samples/input-from-project-to-maintenance-session-put.json
   :language: javascript

Response codes
--------------

.. rest_status_code:: success status.yaml

    - 200
