using System;
using System.Collections.Generic;
using System.Text;

namespace MCS.FOI.CalendarToPDF
{
    public interface ICalendarFileProcessor
    {
        public (string, string, Stream) ProcessCalendarFiles();

        public string SourcePath { get; set; }

        public string DestinationPath { get; set; }

        public string FileName { get; set; }

        public int FailureAttemptCount { get; set; }

        public int WaitTimeinMilliSeconds { get; set; }

        public string Message { get; set; }

    }
}
