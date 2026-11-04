export const setupBlankCodeCommentsFilter = (instance) => {
  let showOnlyEmpty = false;
  const document = instance.UI.iframeWindow.document;

  const isEmptyComment = (annotation) => {
    const contents = annotation.getContents();
    return !contents || contents.trim() === "";
  };

  const applyEmptyFilter = () => {
    // Create a new function each time so the Comments Panel re-renders.
    instance.UI.setCustomNoteFilter(
      (annotation) => !showOnlyEmpty || isEmptyComment(annotation),
    );
  };

  applyEmptyFilter();

  instance.UI.NotesPanel.setCustomHeader({
    overwriteDefaultHeader: false,
    render: () => {
      const wrap = document.createElement("label");
      wrap.style.cssText =
        "display:flex; align-items:left; gap:8px; padding:8px 12px; font-size:13px;";

      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = showOnlyEmpty;
      checkbox.addEventListener("change", (event) => {
        showOnlyEmpty = event.target.checked;
        applyEmptyFilter();
      });

      wrap.append(checkbox, "Blank code");
      return wrap;
    },
  });
};