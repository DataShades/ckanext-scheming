import type { IconButtonProps } from "@rjsf/utils";

function faButton(iconClass: string, extraClass = "btn-primary") {
  return function FaIconButton(props: IconButtonProps) {
    const { icon, iconType, uiSchema, registry, className, ...buttonProps } = props;
    return (
      <button
        type="button"
        aria-label={typeof icon === "string" ? icon : undefined}
        {...buttonProps}
        className={["btn", extraClass, className].filter(Boolean).join(" ")}
      >
        <i className={iconClass} aria-hidden="true" />
      </button>
    );
  };
}

export const faButtonTemplates = {
  AddButton: faButton("fas fa-plus"),
  CopyButton: faButton("fas fa-copy"),
  MoveDownButton: faButton("fas fa-arrow-down"),
  MoveUpButton: faButton("fas fa-arrow-up"),
  RemoveButton: faButton("fas fa-trash", "btn-danger"),
};
