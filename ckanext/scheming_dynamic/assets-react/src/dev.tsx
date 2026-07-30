import "./main";

// A trimmed stand-in for ckanext.scheming_dynamic.schema.DatasetSchema.build()
// enough to sanity-check $ref/$defs/oneOf resolution against RJSF before
// wiring the real thing into CKAN.
const sampleSchema = {
  $schema: "https://json-schema.org/draft/2020-12/schema",
  title: "ckanext-scheming dataset schema",
  type: "object",
  required: ["about", "dataset_type", "dataset_fields", "resource_fields"],
  properties: {
    about: { type: "string", title: "About", minLength: 1 },
    dataset_type: { type: "string", title: "Dataset type", minLength: 1 },
    dataset_fields: { type: "array", minItems: 1, items: { $ref: "#/$defs/field" } },
    resource_fields: { type: "array", minItems: 1, items: { $ref: "#/$defs/field" } },
  },
  $defs: {
    i18n_text: {
      oneOf: [
        { title: "Text", type: "string" },
        { title: "No label", type: "null" },
      ],
    },
    field: {
      type: "object",
      title: "Field",
      required: ["field_name"],
      properties: {
        field_name: { type: "string", minLength: 1, title: "Field name" },
        label: { $ref: "#/$defs/i18n_text", title: "Label" },
        required: { type: "boolean", title: "Required" },
      },
    },
  },
};

const container = document.getElementById("preview")!;
window.SchemingReactEditor.create(container, {
  schema: sampleSchema,
  startval: { about: "", dataset_type: "dataset", dataset_fields: [], resource_fields: [] },
});
