from collections.abc import Callable
from functools import partial
from typing import Any, cast

import ckan.plugins as p
import ckan.plugins.toolkit as tk
from ckan import types
from ckan.common import CKANConfig

from ckanext.scheming_dynamic import views
from ckanext.scheming_dynamic.cli import get_commands


@tk.blanket.actions
@tk.blanket.cli(get_commands)
@tk.blanket.auth_functions
@tk.blanket.validators
@tk.blanket.blueprints(views.get_blueprints)
class SchemingDynamicPlugin(p.SingletonPlugin):
    # TODO: can we use blanket or we want to support old CKAN versions?
    p.implements(p.IMiddleware, inherit=True)
    p.implements(p.IConfigurer)

    # IConfigurer

    def update_config(self, config: CKANConfig) -> None:
        tk.add_template_directory(config, "templates")
        tk.add_resource("assets", "scheming-dynamic")

    # IMiddleware

    def make_middleware(self, app: types.CKANApp, config: CKANConfig) -> types.CKANApp:
        # url_for("<type>.read") for types created after startup
        if hasattr(app, "url_build_error_handlers"):
            app.url_build_error_handlers.append(
                cast(
                    "Callable[[Exception, str, dict[str, Any]], str]",
                    partial(views.build_dynamic_type_url, app),
                )
            )
        return app
