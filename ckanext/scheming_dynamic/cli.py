from __future__ import annotations

import json
from pathlib import Path

import click

from ckanext.scheming_dynamic.schema import SCHEMA_CLASSES
from ckanext.scheming_dynamic.validator import error_location, iter_errors, load_data

entity_type_option = click.option(
    "-t",
    "--type",
    "entity_type",
    type=click.Choice(sorted(SCHEMA_CLASSES)),
    default="dataset",
    show_default=True,
    help="Which ckanext-scheming schema shape to build/validate against.",
)


@click.group(short_help="scheming_dynamic commands")
def scheming_dynamic():
    """scheming_dynamic commands."""


@scheming_dynamic.command()
@entity_type_option
def validation_schema(entity_type: str):
    """Output the JSON Schema for the given entity type.

    Used to validate ckanext-scheming schemas.

    ckan scheming-dynamic validation-schema --type dataset > dataset_schema.schema.json
    """
    click.echo(json.dumps(SCHEMA_CLASSES[entity_type]().build(), indent=2))


@scheming_dynamic.command()
@entity_type_option
@click.argument("schema_file", nargs=-1, required=True, type=click.Path(exists=True))
@click.pass_context
def validate(ctx, entity_type: str, schema_file: list[str]):
    """Validate ckanext-scheming schema file(s).

    Validates against JSON Schema for --type (default: dataset).

    ckan scheming-dynamic validate path/to/schema.yaml [more-schemas.json ...]
    """
    any_errors = False
    schema_instance = SCHEMA_CLASSES[entity_type]()

    for f in schema_file:
        data = load_data(Path(f))
        errors = list(iter_errors(data, schema_instance))

        click.secho(f"Validating schema {f}", fg="green")

        if not errors:
            click.secho("OK - no schema violations", fg="cyan")
            continue

        any_errors = True

        for error in errors:
            click.secho(f"  [{error_location(error)}] {error.message}", fg="red")

    ctx.exit(1 if any_errors else 0)


def get_commands() -> list[click.Command]:
    return [scheming_dynamic]
