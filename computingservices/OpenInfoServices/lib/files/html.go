package files

import (
	"bytes"
	"html/template"
)

type MetaTag struct {
	Name    string
	Content string
}

type Link struct {
	FileName string
	URL      string
}

type TemplateVariables struct {
	Title    string
	MetaTags []MetaTag
	Links    []Link
	Content  string
}

func CreateHTML(variables TemplateVariables) bytes.Buffer {
	// Parse the HTML template file
	t, err := template.ParseFiles("./templates/template.html")
	if err != nil {
		panic(err)
	}

	// Create a buffer to hold the rendered template
	var buf bytes.Buffer

	// Execute the template and write the output to the file
	err = t.Execute(&buf, variables)
	if err != nil {
		panic(err)
	}

	// fmt.Println(buf.String())
	return buf
}
