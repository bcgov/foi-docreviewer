package types

type AnalyzeResults struct {
	AnalyzeResult struct {
		Content string `json:"content"`
		Pages   []struct {
			PageNumber int `json:"pageNumber"`
			Lines      []struct {
				Content string `json:"content"`
			} `json:"lines"`
		} `json:"pages"`
	} `json:"analyzeResult"`
}
