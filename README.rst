===============================
fenix
===============================

OpenStack host maintenance and upgrade in interaction with application

Fenix implements rolling infrastructure maintenance and upgrade in interaction
with application on top of it. In Telco world we talk about VNFM, but one can
implement own simple manager for any application.

Infrastructure admin can call Fenix API to start a maintenance workflow
session. This session will make needed maintenance and upgrade operations to
infrastructure in interaction with application manager to guarantee zero down
time for its service. Interaction gives ability for application manager to
know about new capabilities coming over maintenance to make his own upgrade.
Application can have a time window to finish what he is doing, make own action
to re-instantiate his instance or have Fenix to make migration. Also scaling
application or retirement will be possible.

As Fenix will have project specific messaging with information about instances
affected towards application manager, it will also have admin level messaging.
This messaging can tell what host is down for maintenance, so any
infrastructure components can have this information. Special case for this
would also be telling about adding or removing a host.

* Free software: Apache license
* Documentation: https://wiki.openstack.org/wiki/Fenix
* Wiki: https://wiki.openstack.org/wiki/Fenix
* Source: https://git.openstack.org/cgit/openstack/fenix
* Launchpad: https://launchpad.net/fenix
* Bugs: https://bugs.launchpad.net/fenix
* Blueprints: https://blueprints.launchpad.net/fenix
* How to contribute: https://docs.openstack.org/infra/manual/developers.html

--------

* TODO
