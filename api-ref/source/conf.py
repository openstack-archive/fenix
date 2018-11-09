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