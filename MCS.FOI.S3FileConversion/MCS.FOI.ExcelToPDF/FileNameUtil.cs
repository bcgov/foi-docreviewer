using System;
using System.Collections.Generic;
using System.IO;
using System.Text;

namespace MCS.FOI.ExcelToPDF
{
    public static class FileNameUtil
    {

        public static string GetFormattedFileName(string filename)
        {
            string invalidcharacters = new string(Path.GetInvalidFileNameChars());
            foreach (var _character in invalidcharacters)
            {
                filename = filename.Contains(_character) ? filename.Replace(_character, '_') : filename;
            }

            return filename;
        }

    }
}
