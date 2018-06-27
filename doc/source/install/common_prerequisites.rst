Prerequisites
-------------

Before you install and configure the fenix service,
you must create a database, service credentials, and API endpoints.

#. To create the database, complete these steps:

   * Use the database access client to connect to the database
     server as the ``root`` user:

     .. code-block:: console

        $ mysql -u root -p

   * Create the ``fenix`` database:

     .. code-block:: none

        CREATE DATABASE fenix;

   * Grant proper access to the ``fenix`` database:

     .. code-block:: none

        GRANT ALL PRIVILEGES ON fenix.* TO 'fenix'@'localhost' \
          IDENTIFIED BY 'FENIX_DBPASS';
        GRANT ALL PRIVILEGES ON fenix.* TO 'fenix'@'%' \
          IDENTIFIED BY 'FENIX_DBPASS';

     Replace ``FENIX_DBPASS`` with a suitable password.

   * Exit the database access client.

     .. code-block:: none

        exit;

#. Source the ``admin`` credentials to gain access to
   admin-only CLI commands:

   .. code-block:: console

      $ . admin-openrc

#. To create the service credentials, complete these steps:

   * Create the ``fenix`` user:

     .. code-block:: console

        $ openstack user create --domain default --password-prompt fenix

   * Add the ``admin`` role to the ``fenix`` user:

     .. code-block:: console

        $ openstack role add --project service --user fenix admin

   * Create the fenix service entities:

     .. code-block:: console

        $ openstack service create --name fenix --description "fenix" fenix

#. Create the fenix service API endpoints:

   .. code-block:: console

      $ openstack endpoint create --region RegionOne \
        fenix public http://controller:XXXX/vY/%\(tenant_id\)s
      $ openstack endpoint create --region RegionOne \
        fenix internal http://controller:XXXX/vY/%\(tenant_id\)s
      $ openstack endpoint create --region RegionOne \
        fenix admin http://controller:XXXX/vY/%\(tenant_id\)s
