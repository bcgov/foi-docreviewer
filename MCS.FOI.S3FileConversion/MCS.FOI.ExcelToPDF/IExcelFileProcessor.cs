using System;
using System.Collections.Generic;
using System.Text;

namespace MCS.FOI.ExcelToPDF
{
    public interface IExcelFileProcessor
    {
        public (bool, string, string, Stream) ConvertToPDF();

        public string ExcelSourceFilePath { get; set; }

        public string PdfOutputFilePath { get; set; }

        public string ExcelFileName { get; set; }

        public bool IsSinglePDFOutput { get; set; }

        public int FailureAttemptCount { get; set; }

        public int WaitTimeinMilliSeconds { get; set; }
    }
}
