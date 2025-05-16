package types

// Root struct for the response
type AnalyzeResults struct {
	Status              string        `json:"status"`
	CreatedDateTime     string        `json:"createdDateTime"`
	LastUpdatedDateTime string        `json:"lastUpdatedDateTime"`
	AnalyzeResult       AnalyzeResult `json:"analyzeResult"`
}

// AnalyzeResult contains the main analysis output
type AnalyzeResult struct {
	APIVersion    string         `json:"apiVersion"`
	ModelID       string         `json:"modelId"`
	Content       string         `json:"content"`
	Pages         []Page         `json:"pages"`
	Tables        []Table        `json:"tables"`
	KeyValuePairs []KeyValuePair `json:"keyValuePairs"`
	Entities      []Entity       `json:"entities"`
	Styles        []Style        `json:"styles"`
	Paragraphs    []Paragraph    `json:"paragraphs"`
}

// Page represents details of a single page
type Page struct {
	PageNumber int     `json:"pageNumber"`
	Angle      float64 `json:"angle"`
	Width      float64 `json:"width"`
	Height     float64 `json:"height"`
	Unit       string  `json:"unit"`
	Lines      []Line  `json:"lines"`
	Words      []Word  `json:"words"`
}

// Line represents a line of text
type Line struct {
	Content         string           `json:"content"`
	BoundingRegions []BoundingRegion `json:"boundingRegions"`
	Spans           []Span           `json:"spans"`
}

// Word represents an individual word
type Word struct {
	Content     string    `json:"content"`
	BoundingBox []float64 `json:"boundingBox"`
	Confidence  float64   `json:"confidence"`
}

// Table represents a detected table
type Table struct {
	RowCount        int              `json:"rowCount"`
	ColumnCount     int              `json:"columnCount"`
	BoundingRegions []BoundingRegion `json:"boundingRegions"`
	Cells           []Cell           `json:"cells"`
}

// Cell represents a cell in a table
type Cell struct {
	Kind            string           `json:"kind"`
	RowIndex        int              `json:"rowIndex"`
	ColumnIndex     int              `json:"columnIndex"`
	Content         string           `json:"content"`
	BoundingRegions []BoundingRegion `json:"boundingRegions"`
	Spans           []Span           `json:"spans"`
}

// KeyValuePair represents a key-value pair extracted from the document
type KeyValuePair struct {
	Key   KVElement `json:"key"`
	Value KVElement `json:"value"`
}

// KVElement represents the key or value in a key-value pair
type KVElement struct {
	Content         string           `json:"content"`
	BoundingRegions []BoundingRegion `json:"boundingRegions"`
	Spans           []Span           `json:"spans"`
}

// Entity represents a named entity
type Entity struct {
	Category        string           `json:"category"`
	Content         string           `json:"content"`
	Confidence      float64          `json:"confidence"`
	BoundingRegions []BoundingRegion `json:"boundingRegions"`
	Spans           []Span           `json:"spans"`
}

// Style represents text styles
type Style struct {
	IsHandwritten bool    `json:"isHandwritten"`
	Spans         []Span  `json:"spans"`
	Confidence    float64 `json:"confidence"`
}

// Paragraph represents a paragraph of text
type Paragraph struct {
	Content         string           `json:"content"`
	BoundingRegions []BoundingRegion `json:"boundingRegions"`
	Spans           []Span           `json:"spans"`
}

// BoundingRegion represents the location of an element on a page
type BoundingRegion struct {
	PageNumber  int       `json:"pageNumber"`
	BoundingBox []float64 `json:"boundingBox"`
}

// Span represents a range of text offsets
type Span struct {
	Offset int `json:"offset"`
	Length int `json:"length"`
}
