import React from "react";
import spinner from "../assets/spinner.gif";


const DocumentLoader = React.memo(({ costumStyle }) => (
  <img
    className="loader"
    src={spinner}
    alt="Loading ..."
    style={costumStyle}
  />
));
export default DocumentLoader;

