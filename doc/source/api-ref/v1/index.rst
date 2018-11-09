:tocdepth: 2

#######################
Host Maintenance API v1
#######################

.. rest_expand_all::

#####
Admin
#####

These APIs are meant for infrastructure admin who is in charge of triggering
the rolling maintenance and upgrade workflows.

.. include:: maintenance.inc

#######
Project
#######

These APIs are meant for projects having instances on top of the infrastructure
under corresponding rolling maintenance or upgrade session. Usage of these APIs
expects there is an application manager (VNFM) that can interact with Fenix
workflow via these APIs. If this is not the case, workflow should have a default
behavior for instances owned by projects, that are not interacting with Fenix.

.. include:: project.inc
