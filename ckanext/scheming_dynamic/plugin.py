import ckan.plugins as p

from ckanext.scheming_dynamic.cli import get_commands


class SchemingDynamicPlugin(p.SingletonPlugin):
    p.implements(p.IClick)

    # IClick

    def get_commands(self):
        return get_commands()
