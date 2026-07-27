from functools import partial

import ckan.plugins as p
from ckan import types
from ckan.common import CKANConfig

from ckanext.scheming_dynamic import views
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
    p.implements(p.IBlueprint)
    p.implements(p.IMiddleware, inherit=True)

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

    # IBlueprint

    def get_blueprint(self):
        return views.get_blueprints()

    # IMiddleware

    def make_middleware(self, app: types.CKANApp, config: CKANConfig) -> types.CKANApp:
        # url_for("<type>.read") for types created after startup
        if hasattr(app, "url_build_error_handlers"):
            app.url_build_error_handlers.append(partial(views.build_dynamic_type_url, app))
        return app
