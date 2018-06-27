2. Edit the ``/etc/fenix/fenix.conf`` file and complete the following
   actions:

   * In the ``[database]`` section, configure database access:

     .. code-block:: ini

        [database]
        ...
        connection = mysql+pymysql://fenix:FENIX_DBPASS@controller/fenix
