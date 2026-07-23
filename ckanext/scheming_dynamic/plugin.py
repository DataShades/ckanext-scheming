import ckan.plugins as p

from ckanext.scheming_dynamic.cli import get_commands
from ckanext.scheming_dynamic.logic.action import get_actions
from ckanext.scheming_dynamic.logic.auth import get_auth_functions
from ckanext.scheming_dynamic.logic.validators import get_validators


class SchemingDynamicPlugin(p.SingletonPlugin):
    # TODO: can we use blanket or we want to support old CKAN versions?
    p.implements(p.IClick)
    p.implements(p.IActions)
    p.implements(p.IAuthFunctions)
    p.implements(p.IValidators)

    # IClick

    def get_commands(self):
        return get_commands()

    # IActions

    def get_actions(self):
        return get_actions()

    # IAuthFunctions

    def get_auth_functions(self):
        return get_auth_functions()

    # IValidators

    def get_validators(self):
        return get_validators()
