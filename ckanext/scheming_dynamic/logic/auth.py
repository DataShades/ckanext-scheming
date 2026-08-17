from __future__ import annotations

from ckan import types


def scheming_schema_create(
    context: types.Context, data_dict: types.DataDict
) -> types.AuthResult:
    """Only sysadmins can create dynamic dataset schemas."""
    return {"success": False}


def scheming_schema_update(
    context: types.Context, data_dict: types.DataDict
) -> types.AuthResult:
    """Only sysadmins can update dynamic dataset schemas."""
    return {"success": False}


def scheming_schema_delete(
    context: types.Context, data_dict: types.DataDict
) -> types.AuthResult:
    """Only sysadmins can delete dynamic dataset schemas."""
    return {"success": False}


def scheming_preset_create(
    context: types.Context, data_dict: types.DataDict
) -> types.AuthResult:
    """Only sysadmins can create field presets."""
    return {"success": False}


def scheming_preset_update(
    context: types.Context, data_dict: types.DataDict
) -> types.AuthResult:
    """Only sysadmins can update field presets."""
    return {"success": False}


def scheming_preset_delete(
    context: types.Context, data_dict: types.DataDict
) -> types.AuthResult:
    """Only sysadmins can delete field presets."""
    return {"success": False}


def scheming_schema_activity_list(
    context: types.Context, data_dict: types.DataDict
) -> types.AuthResult:
    """Only sysadmins can view dynamic schema history."""
    return {"success": False}


def get_auth_functions():
    return {
        "scheming_schema_create": scheming_schema_create,
        "scheming_schema_update": scheming_schema_update,
        "scheming_schema_delete": scheming_schema_delete,
        "scheming_schema_activity_list": scheming_schema_activity_list,
        "scheming_preset_create": scheming_preset_create,
        "scheming_preset_update": scheming_preset_update,
        "scheming_preset_delete": scheming_preset_delete,
    }
