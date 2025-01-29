import {
    faCircleHalfStroke, faCircle, faCircleQuestion, faSpinner,
    faCircleStop, faCircleXmark, faBookmark, faLayerGroup
} from '@fortawesome/free-solid-svg-icons';
import { faCircle as filledCircle } from '@fortawesome/free-regular-svg-icons';

export const PAGE_FLAGS = {

    1:"Partial Disclosure",
    2:"Full Disclosure",
    3:"Withheld in Full",
    4:"Consult",
    5:"Duplicate",
    6:"Not Responsive",
    7:"In Progress",
    8:"Page Left Off",
    9:"Phases"    
};

export const pageFlagIcons: any = {
    1: faCircleHalfStroke,
    "Partial Disclosure": faCircleHalfStroke,
    2: filledCircle,
    "Full Disclosure": filledCircle,
    3: faCircle,
    "Withheld in Full": faCircle,
    4: faCircleQuestion,
    "Consult": faCircleQuestion,
    5: faCircleStop,
    "Duplicate": faCircleStop,
    6: faCircleXmark,
    "Not Responsive": faCircleXmark,
    7: faSpinner,
    "In Progress": faSpinner,
    8: faBookmark,
    "Page Left Off": faBookmark,
    9: faLayerGroup,
    "Phases": faLayerGroup,
};


