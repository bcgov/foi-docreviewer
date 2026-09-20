package types

// AnalyzeSource is the document handed to Azure Analyze: base64 bytes
// (default) or a presigned URL Azure fetches itself. Exactly one field is set.
type AnalyzeSource struct {
	Base64 string
	URL    string
}
