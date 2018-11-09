.. _baseworkflow:

==================
Fenix BaseWorkflow
==================

BaseWorkFlow class implemented in '/fenix/workflow/workflow.py' is the one you
inherit when creating your own workflow. Example workflow 'default.py' using
this can be found from the workflow directory '/fenix/workflow/workflows'.

The class provides the access to all maintenance session related data and the
ability to send Fenix notifications and process the incoming API requests.

There is also a dictionary describing the generic workflow states that should be
supported:

.. code-block:: json

    {
        "MAINTENANCE": "maintenance",
        "SCALE_IN": "scale_in",
        "PREPARE_MAINTENANCE": "prepare_maintenance",
        "START_MAINTENANCE": "start_maintenance",
        "PLANNED_MAINTENANCE": "planned_maintenance",
        "MAINTENANCE_COMPLETE": "maintenance_complete",
        "MAINTENANCE_DONE": "maintenance_done",
        "MAINTENANCE_FAILED": "maintenance_failed"
    }

Key is the state name and value is the internal method that you
iplement in your workflow to handle that state. When the method returns, it
will be checked from Class variable 'self.state' what is the next method to be
called. So your state related method should change 'self.state' to what you
want to do next. The method should also implement calling of any action plug-ins
and other state related functionality like sending notifications.

States
======

Here is what is supposed to be done in different states when also utilizing
the default workflow.

MAINTENANCE
-----------

This is the initial state right after infrastructure admin has created the
maintenance session.

Here one should check if all projects are subscribed to AODH event alarm for
event type 'maintenance.planned'. If project supports this, one can assume we
can have interaction with that project manager (VNFM). If not, we should have some
default handling for project instances during rolling maintenance, or we should
decide to go to state 'MAINTENANCE_FAILED' as we do not support that kind of
project. From here onwards, we assume projects support this interaction, so
can better define other coming states.

Next, we send 'maintenance.planned' notification with state 'MAINTENANCE' to
each project. We wait for the duration of 'self.conf.project_maintenance_reply'
the reply or fail if some project did not reply. After all projects are in state
'ACK_MAINTENANCE' we can wait until the time is 'self.session.maintenance_at'
and then start the actual maintenance.

When it is time to start we might call the type 'pre' action plugins to make
actions needed before rolling host by host forwards. This might include
downloading of needed software changes and already doing some actions for
controllers in case of maintenance operation like OpenStack upgrade.

If currently all the compute capacity is in use and we want to have
an empty compute that we can maintain first, we should have 'self.state' as
'SCALE_IN' to scale down the application. If there is capacity, but no empty
host (assuming we want to make maintenance only to empty host), we can have
'self.state' as 'PREPARE_MAINTENANCE' to move instances around to have an empty
host if possible. In case we had an empty host, we can go straight put
'self.state' to 'START_MAINTENANCE' to start maintenance on that host.

SCALE_IN
--------

We send 'maintenance.planned' notification with state 'SCALE_IN' to each
project. We wait duration of 'self.conf.project_scale_in_reply' the reply or
fail if some project did not reply. After all projects are in the state
'ACK_SCALE_IN' we can repeat the same checks as in state 'MAINTENANCE' to
decide is 'self.state' should be 'SCALE_IN', 'PREPARE_MAINTENANCE' or
'START_MAINTENANCE'. Again on any error we always put 'self.state' to
'MAINTENANCE_FAILED'

PREPARE_MAINTENANCE
-------------------

As we have some logic to figure out the host that we can make empty, we can 
send 'maintenance.planned' notification with state 'PREPARE_MAINTENANCE' to each
project having instances on that host. We wait for the duration of
'self.conf.project_maintenance_reply' the reply or fail if some project did
not reply. After all affected projects are in state 'ACK_PREPARE_MAINTENANCE' we
can check project and instance specific answer and make action given like
'migrate' to move instances away from the host. After the action is done we will
send 'maintenance.planned' for each each instance with the state
'INSTANCE_ACTION_DONE' and with the corresponding 'instance_id'.

Next, we should be able to put 'self.state'to 'START_MAINTENANCE'.

START_MAINTENANCE
-----------------

In case no hosts are maintained yet, we can go through all empty compute hosts in
the maintenance session:

    We send 'maintenance.host' notification with state 'IN_MAINTENANCE' for
    each host before we start to maintain it. Then we run action plug-ins of
    type 'host'
    in the order they are defined to run. After we are ready with the
    maintenance actions we send 'maintenance.host' notification with state
    'MAINTENANCE_COMPLETE'.
    
    When all empty computes are maintained we can put 'self.state' to
    'PLANNED_MAINTENANCE'.

In case all empty hosts were already maintained, we could pick empty host that
we have after 'PLANNED_MAINTENANCE' is run on some compute host:

    We send 'maintenance.host' notification with state 'IN_MAINTENANCE' before
    we start to maintain the host. Then we run action plug-ins of type 'host' in
    the order they are defined to run. After we are ready with the maintenance
    actions we send 'maintenance.host' notification with state
    'MAINTENANCE_COMPLETE'.
    
    When all empty computes are maintained we can put 'self.state' to
    'PLANNED_MAINTENANCE' or if all compute hosts are maintained we can put
    'self.state' to 'MAINTENANCE_COMPLETE'.

PLANNED_MAINTENANCE
-------------------

We find a host that has not been maintained yet and contains instances. After
choosing the host, we can send 'maintenance.planned' notification with state
'PLANNED_MAINTENANCE' to each project having instances on the host. After all
affected projects are in state 'ACK_PLANNED_MAINTENANCE' we can check project
and instance specific answer and make action given like 'migrate' to move
instances away from the host. After the action is done we will send
'maintenance.planned' with the state 'INSTANCE_ACTION_DONE' with the
'instance_id' for the instance action was completed. It might also be that
the project manager did already an own to re-instantiate, so we do not have to
do any action.

When the project manager receives 'PLANNED_MAINTENANCE' it also knows that
instances will now be moved to the already maintained host. With the payload,
there will also go 'metadata' that can indicate new capabilities the project is
getting when instances are moving. It might be for example:

  "metadata": {"openstack_version": "Queens"}
  
It might be nice to make the application (VNF) upgrade now at the same time
when instances are anyhow moved to new compute host with new capabilities.

Next, when all instances are moved and the host is empty, we can put
'self.state' to 'START_MAINTENANCE'

MAINTENANCE_COMPLETE
--------------------

Now all instances have been moved to already maintained compute hosts and all 
compute host are maintained. Next, we might run action 'post' type of action
plug-ins to finalize maintenance.

When this is done we can send 'maintenance.planned' notification with state
'MAINTENANCE_COMPLETE' to each project. In case projects scaled down at the
beginning of the maintenance they can now scale back to full operation. After
all projects are in state 'ACK_MAINTENANCE_COMPLETE' we can change the
'self.state' to 'MAINTENANCE_DONE'

MAINTENANCE_DONE
----------------

This will now make the maintenance session idle until infrastructure admin will
delete it.

MAINTENANCE_FAILED
------------------

This will now make the maintenance session idle until infrastructure admin will
fix and continue the session or delete it.


Future
======

Currently, infrastructure admin needs to poll Fenix API to know the session
state. When notification with the event type 'maintenance.session' gets
implemented, infrastructure admin will be receiving state change whenever it
will change.
