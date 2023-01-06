using System;
using System.Collections.Generic;
using System.Text;

namespace MCS.FOI.ExcelToPDF
{
    public interface IExcelFileProcessor
    {
        public (bool, string, Stream) ConvertToPDF();

        public bool IsSinglePDFOutput { get; set; }

        public int FailureAttemptCount { get; set; }

        public int WaitTimeinMilliSeconds { get; set; }
    }
}
