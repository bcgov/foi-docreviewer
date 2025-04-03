

export const createSettingsDropDownMenu = (document) => {
    const menu = document.createElement("div");
    menu.classList.add("Overlay");
    menu.classList.add("FlyoutMenu");
    menu.id = "setting_menu";
    menu.style.right = "auto";
    menu.style.top = "30px";
    menu.style.minWidth = "250px";
    menu.style.padding = "10px";
    menu.style.display = "none";
    
    menu.addEventListener("click", () => { 
        document.getElementById("setting_menu").style.display = "inline";
    })
  
    return menu;
  };

  export const  createSeperator = (document)=>{
      // Create separator line
      const separator = document.createElement("hr");
      separator.style.border = "none";
      separator.style.borderTop = "1px solid #ccc";
      separator.style.margin = "5px 0";

      return separator;
  }

  // Function to create a category header
export const createCategoryHeader = (document,text) => {
  const header = document.createElement("div");
  header.textContent = text;
  header.style.fontWeight = "bold";
  header.style.padding = "5px 0";
  header.style.borderBottom = "2px solid #ddd"; // Header separator
  header.style.marginTop = "10px";
  header.style.width = "100%"
  header.style.fontWeight = "bold";
  return header;
};


  export const createPIIToggleButton = (document,setPIIDetection) => {
    const container = document.createElement("div");
    container.style.display = "flex";
    container.style.alignItems = "center";
    container.style.gap = "10px";
    container.style.padding ="15px"

    // Label for toggle switch
    const label = document.createElement("label");
    label.style.display = "flex";
    label.style.alignItems = "center";
    label.style.cursor = "pointer";
    label.style.gap = "8px";
    label.textContent = "PII Detection";

    // Toggle switch container
    const switchContainer = document.createElement("div");
    switchContainer.style.position = "relative";
    switchContainer.style.width = "40px";
    switchContainer.style.height = "20px";
    switchContainer.style.borderRadius = "20px";
    switchContainer.style.background = "#ccc";
    switchContainer.style.transition = "background 0.3s";

    // Switch button (circle)
    const switchButton = document.createElement("div");
    switchButton.style.position = "absolute";
    switchButton.style.top = "2px";
    switchButton.style.left = "2px";
    switchButton.style.width = "16px";
    switchButton.style.height = "16px";
    switchButton.style.borderRadius = "50%";
    switchButton.style.background = "#fff";
    switchButton.style.transition = "left 0.3s";

    switchContainer.appendChild(switchButton);

    // Toggle functionality
    let isOn = false;
    switchContainer.addEventListener("click", () => {
      isOn = !isOn;
      switchContainer.style.background = isOn ? "#4CAF50" : "#ccc"; // Green for ON, Gray for OFF
      switchButton.style.left = isOn ? "22px" : "2px"; // Move switch button
      setPIIDetection(isOn)
           
    });

    // Assemble elements
    container.appendChild(label);
    container.appendChild(switchContainer);

    return container;
  };

  export const createCategorySelector = (document,setPIICategories) => {
    const container = document.createElement("div");
    container.style.display = "flex";
    container.style.alignItems = "center";
    container.style.gap = "10px";
    container.style.padding ="15px"

    // Label for toggle switch
    const label = document.createElement("label");
    label.style.display = "flex";
    label.style.alignItems = "center";
    label.style.cursor = "pointer";
    label.style.gap = "8px";
    label.textContent = "Categories";

    const select = document.createElement("select")
    select.setAttribute("multiple", true)

    const personOption = document.createElement("option")
    personOption.setAttribute("value", "Person")
    personOption.textContent = "Person"
    personOption.selected = true;
    const emailOption = document.createElement("option")
    emailOption.setAttribute("value", "Email")
    emailOption.textContent = "Email"
    emailOption.selected = true;
    const orgOption = document.createElement("option")
    orgOption.setAttribute("value", "Organization")
    orgOption.textContent = "Organization"
    select.appendChild(emailOption)
    select.appendChild(personOption)
    select.appendChild(orgOption)

    select.addEventListener("change", (event) => {
      setPIICategories([...event.target.selectedOptions].map(o => o.value))
           
    });

    // Assemble elements
    container.appendChild(label);
    container.appendChild(select);

    return container;
  };
  
  export const renderCustomSettingsButton = (document, menu) => {
    const menuBtn = document.createElement("button");
    //menuBtn.textContent = "Settings";
    menuBtn.innerHTML =`<svg width="20" height="20" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg"><path clip-rule="evenodd" d="M9 0H7l-.55 2.202a6 6 0 0 0-1.453.602L3.05 1.636 1.636 3.05l1.168 1.947c-.26.45-.464.938-.602 1.452L0 7v2l2.202.55q.209.774.602 1.453L1.636 12.95l1.414 1.414 1.947-1.168c.45.26.938.465 1.452.602L7 16h2l.55-2.202a6 6 0 0 0 1.453-.602l1.947 1.168 1.414-1.414-1.168-1.947c.26-.45.465-.938.602-1.452L16 9V7l-2.202-.55a6 6 0 0 0-.602-1.453l1.168-1.947-1.414-1.414-1.947 1.168a6 6 0 0 0-1.452-.602zM8 10a2 2 0 1 0 0-4 2 2 0 0 0 0 4" fill="#030708" fill-rule="evenodd"/></svg>`;
    menuBtn.id = "foiSettings";
    menuBtn.style.background = 'transparent'
    menuBtn.style.border = 'none'
    menuBtn.padding = "5px"  
    menuBtn.onclick = async () => {
        if (menu.style.display === "flex") {
            menu.style.display = "none";
          } else {
            menu.style.left = `${
              document.body.clientWidth - (menuBtn.clientWidth + 330)
            }px`;
            menu.style.display = "flex";
          }
    };
  
    return menuBtn;
  };

 export const createTextToggle = (document, redactiontool)=>{
    const container = document.createElement("div");
    container.style.display = "flex";
    container.style.alignItems = "center";
    container.style.gap = "10px";
    container.style.padding ="15px"

    // Label for toggle switch
    const label = document.createElement("label");
    label.style.display = "flex";
    label.style.alignItems = "center";
    label.style.cursor = "pointer";
    label.style.gap = "8px";
    label.textContent = "Text Selection";

    // Toggle switch container
    const switchContainer = document.createElement("div");
    switchContainer.style.position = "relative";
    switchContainer.style.width = "40px";
    switchContainer.style.height = "20px";
    switchContainer.style.borderRadius = "20px";
    switchContainer.style.background = "#ccc";
    switchContainer.style.transition = "background 0.3s";

    // Switch button (circle)
    const switchButton = document.createElement("div");
    switchButton.style.position = "absolute";
    switchButton.style.top = "2px";
    switchButton.style.left = "2px";
    switchButton.style.width = "16px";
    switchButton.style.height = "16px";
    switchButton.style.borderRadius = "50%";
    switchButton.style.background = "#fff";
    switchButton.style.transition = "left 0.3s";

    switchContainer.appendChild(switchButton);

    // Toggle functionality
    let isOn = false;
    switchContainer.addEventListener("click", () => {
      isOn = !isOn;
      switchContainer.style.background = isOn ? "#4CAF50" : "#ccc"; // Green for ON, Gray for OFF
      switchButton.style.left = isOn ? "22px" : "2px"; // Move switch button
      if(isOn)
      {
        redactiontool.disableAutoSwitch()
      }
      else{
        redactiontool.enableAutoSwitch()
      }
     
    });

    // Assemble elements
    container.appendChild(label);
    container.appendChild(switchContainer);

    return container;
 }


 export const createOpacityToggle = (document, setIsRedlineOpaque)=>{
    const container = document.createElement("div");
    container.style.display = "flex";
    container.style.alignItems = "center";
    container.style.gap = "10px";
    container.style.padding ="15px"
    
    // Label for toggle switch
    const label = document.createElement("label");
    label.style.display = "flex";
    label.style.alignItems = "center";
    label.style.cursor = "pointer";
    label.style.gap = "8px";
    label.textContent = "Opacity";

    // Toggle switch container
    const switchContainer = document.createElement("div");
    switchContainer.style.position = "relative";
    switchContainer.style.width = "40px";
    switchContainer.style.height = "20px";
    switchContainer.style.borderRadius = "20px";
    switchContainer.style.background = "#ccc";
    switchContainer.style.transition = "background 0.3s";

    // Switch button (circle)
    const switchButton = document.createElement("div");
    switchButton.style.position = "absolute";
    switchButton.style.top = "2px";
    switchButton.style.left = "2px";
    switchButton.style.width = "16px";
    switchButton.style.height = "16px";
    switchButton.style.borderRadius = "50%";
    switchButton.style.background = "#fff";
    switchButton.style.transition = "left 0.3s";

    switchContainer.appendChild(switchButton);

    // Toggle functionality
    let isOn = false;
    switchContainer.addEventListener("click", () => {
      isOn = !isOn;
      switchContainer.style.background = isOn ? "#4CAF50" : "#ccc"; // Green for ON, Gray for OFF
      switchButton.style.left = isOn ? "22px" : "2px"; // Move switch button
      setIsRedlineOpaque(isOn)
     
    });

    // Assemble elements
    container.appendChild(label);
    container.appendChild(switchContainer);

    return container;
 }