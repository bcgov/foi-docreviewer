using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace MCS.FOI.DocToPDF
{
    public interface IDocFileProcessor
    {
        public int FailureAttemptCount { get; set; }

        public int WaitTimeinMilliSeconds { get; set; }

        public bool IsSinglePDFOutput { get; set; }


    }
}
