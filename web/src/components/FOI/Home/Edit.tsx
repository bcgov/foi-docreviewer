import { ReactComponent as EditLogo } from "../../../assets/images/icon-pencil-line.svg";

  const disableMultiSelectEdit = (_selectedAnnotations: any) => {
    if (_selectedAnnotations && _selectedAnnotations.length > 0) {
      return _selectedAnnotations.some(
        (obj: any) =>
          obj.Subject !== "Redact" && obj.getCustomData("sections") === ""
      );
    }
    return true;
  };

  //START: Bulk Edit using Multi Select Option
  const MultiSelectEdit = ({docInstance, editRedactions}: any) => {
    let _selectedAnnotations =
      docInstance?.Core?.annotationManager.getSelectedAnnotations();
    const disableEdit = disableMultiSelectEdit(_selectedAnnotations);
    const _selectedRedactions = _selectedAnnotations?.filter(
      (obj: any) =>
        obj.Subject !== "Redact" && obj.getCustomData("sections") !== ""
    );
    return (
      <button
        type="button"
        className="Button ActionButton"
        style={disableEdit ? { cursor: "default" } : {}}
        onClick={() => {
          editRedactions(
            docInstance?.Core?.annotationManager,
            docInstance?.Core?.annotationManager.exportAnnotations({
              annotationList: _selectedRedactions,
              useDisplayAuthor: true,
            })
          );
        }}
        disabled={disableEdit}
      >
        <div
          className="Icon"
          style={disableEdit ? { color: "#868e9587" } : {}}
        >
          <EditLogo />
        </div>
      </button>
    );
  };
  //END: Bulk Edit using Multi Select Option


  const Edit = ({instance, editAnnotation}: any) => {
    let _selectedAnnotations = instance?.Core?.annotationManager.getSelectedAnnotations();
    const disableEdit = _selectedAnnotations.some(
      (obj: any) =>
        obj.Subject !== "Redact" && obj.getCustomData("sections") === ""
    );
    const _selectedRedaction = _selectedAnnotations.filter(
      (obj: any) => obj.Subject === "Redact"
    );
    return (
      <button
        type="button"
        className="Button ActionButton"
        style={disableEdit ? { cursor: "default" } : {}}
        onClick={() => {
          editAnnotation(
            instance?.Core?.annotationManager,
            instance?.Core?.annotationManager.exportAnnotations({
              annotationList: _selectedRedaction,
              useDisplayAuthor: true,
            })
          );
        }}
        disabled={disableEdit}
      >
        <div
          className="Icon"
          style={disableEdit ? { color: "#868e9587" } : {}}
        >
          <EditLogo />
        </div>
      </button>
    );
  };

  export { 
    MultiSelectEdit,
    Edit 
  };