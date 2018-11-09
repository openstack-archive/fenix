# This file is not used until the api-ref directory is part of
# the doc folder and the Fenix documentation is published to 
# readthedocs.org
# When Fenix API documentation will be published to [1] and the
# documentation is builded according to [2] this file will be used
# again.
#
# [1]: https://docs.openstack.org/rocky/api/
# [2]: https://docs.openstack.org/doc-contrib-guide/api-guides.html

extensions = [
    'os_api_ref',
    'openstackdocstheme'
]

# The prefix and repo name like
repository_name = 'openstack/fenix'
# Set Launchpad bug tag, default is empty
bug_tag = ''
# The launchpad project name like
bug_project = 'fenix'

html_theme = 'openstackdocs'
html_theme_options = {
    "sidebar_mode": "toc",
}

# The master toctree document.
master_doc = 'index'

# Must set this variable to include year, month, day, hours, and minutes.
html_last_updated_fmt = '%Y-%m-%d %H:%M'