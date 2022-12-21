using System;
using System.Collections.Generic;
using System.Text;

namespace MCS.FOI.CalendarToPDF
{
    public interface ICalendarFileProcessor
    {
        public (bool, string, Stream, Dictionary<MemoryStream, string>) ProcessCalendarFiles();


        public int FailureAttemptCount { get; set; }

        public int WaitTimeinMilliSeconds { get; set; }

        public string Message { get; set; }

    }
}
