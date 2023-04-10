using System;
using System.Collections.Generic;
using System.Text;

namespace MCS.FOI.S3FileConversion.Utilities
{
    /// <summary>
    /// Mapping POCO class to map conversion environment variables to strongly typed objects
    /// </summary>
    public static class ConversionSettings
    {
          
        public static int FailureAttemptCount { get; set; }

        public static int WaitTimeInMilliSeconds { get; set; }

        public static int FileWatcherMonitoringDelayInMilliSeconds { get; set; }
        
        public static int DayCountBehindToStart { get; set; }

        public static string SyncfusionLicense { get; set; }



    }

   
}
