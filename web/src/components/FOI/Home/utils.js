export const getPageNoOfStitchedDoc = (file, page, pageMappedDocs) => {
    let stitchedPageNo = 0;
    let doc = pageMappedDocs?.find((mappedDoc)=>file.documentid === mappedDoc.docId);
    stitchedPageNo = doc?.pageMappings?.find((mappedPage)=>mappedPage.pageNo == page)?.stitchedPageNo;
    return stitchedPageNo;
}
  