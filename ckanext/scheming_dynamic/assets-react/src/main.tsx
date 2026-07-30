import { createRoot, type Root } from "react-dom/client";
import { flushSync } from "react-dom";
import Form from "@rjsf/core";
import validator from "@rjsf/validator-ajv8";
import type { RJSFSchema } from "@rjsf/utils";
import { faButtonTemplates } from "./faButtons";

interface SchemingEditorHandle {
  getValue: () => unknown;
  setValue: (value: unknown) => void;
  validate: () => Array<{ path: string; message: string }>;
  destroy: () => void;
}

interface CreateOptions {
  schema: RJSFSchema;
  startval?: unknown;
}

// RJSF reports error locations as ajv "instancePath"-style strings
// (e.g. ".dataset_fields[0].field_name"). Normalize to the
// "dataset_fields.0.field_name" shape the CKAN module already expects
// from the JSON Editor it replaces.
function formatPath(property: string | undefined): string {
  return (property || "")
    .replace(/^\.+/, "")
    .replace(/\[(\d+)\]/g, ".$1");
}

function create(container: HTMLElement, options: CreateOptions): SchemingEditorHandle {
  const root: Root = createRoot(container);
  let formData: unknown = options.startval ?? {};

  function render(): void {
    root.render(
      <Form
        schema={options.schema}
        validator={validator}
        formData={formData}
        liveValidate={false}
        showErrorList={false}
        templates={{ ButtonTemplates: faButtonTemplates }}
        onChange={(event) => {
          formData = event.formData;
        }}
      >
        {/* Submission is driven by the CKAN form's own submit button. */}
        <></>
      </Form>
    );
  }

  // Synchronous first render so callers can rely on the handle being
  // fully usable as soon as create() returns (matches the JSON Editor
  // constructor this replaces).
  flushSync(render);

  return {
    getValue: () => formData,
    setValue: (value) => {
      formData = value;
      flushSync(render);
    },
    validate: () => {
      const result = validator.validateFormData(formData, options.schema);
      return result.errors.map((error) => ({
        path: formatPath(error.property),
        message: error.message || "",
      }));
    },
    destroy: () => root.unmount(),
  };
}

declare global {
  interface Window {
    SchemingReactEditor: { create: typeof create };
  }
}

window.SchemingReactEditor = { create };
