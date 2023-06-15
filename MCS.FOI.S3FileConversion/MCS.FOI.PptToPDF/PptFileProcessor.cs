
using Serilog;
//using Syncfusion.OfficeChartToImageConverter;
using Syncfusion.Presentation;
using Syncfusion.PresentationRenderer;
//using Syncfusion.PresentationToPdfConverter;
using System.IO;
using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Imaging;
using Syncfusion.Pdf;
using Syncfusion.Drawing;
using Image = System.Drawing.Image;
using ImageFormat = System.Drawing.Imaging.ImageFormat;
using System.Transactions;

using Syncfusion.Pdf;



namespace MCS.FOI.PPTToPDF
{
    public class PptFileProcessor : IPptFileProcessor, IDisposable
    {


        public PptFileProcessor() { }

        public PptFileProcessor(Stream SourceStream)
        {
            this.SourceStream = SourceStream;
        }

        public Stream SourceStream { get; set; }

        public int FailureAttemptCount { get; set; }

        public int WaitTimeinMilliSeconds { get; set; }

        public bool IsSinglePDFOutput { get; set; }


        private MemoryStream? output = null;
        public (bool, Stream) ConvertToPDF()
        {
            bool converted = false;
            string message = string.Empty;
            bool _isSinglePDFOutput = IsSinglePDFOutput;
            output = new MemoryStream();
            try
            {
                for (int attempt = 1; attempt <= FailureAttemptCount && !converted; attempt++)
                {
                    try
                    {

                        using (IPresentation pptxDoc = Presentation.Open(SourceStream))
                        {
                            foreach (ISlide slide in pptxDoc.Slides)
                            {
                                //Check the current slide contains notes slide.
                                if (slide.NotesSlide == null)
                                    slide.AddNotesSlide();
                            }
                            //pptxDoc.ChartToImageConverter = new ChartToImageConverter
                            //{
                            //    ScalingMode = Syncfusion.OfficeChart.ScalingMode.Best
                            //};
                            ConvertEMFToPNG(pptxDoc);
                            //Initialize the PresentationRenderer to perform image conversion.
                            // Add notes slide to the current slide.


                            pptxDoc.PresentationRenderer = new PresentationRenderer();
                            PresentationToPdfConverterSettings pdfConverterSettings = new PresentationToPdfConverterSettings();
                            pdfConverterSettings.PublishOptions = PublishOptions.NotesPages;
                            using (PdfDocument pdfDocument = PresentationToPdfConverter.Convert(pptxDoc, pdfConverterSettings))
                            {
                                
                                //Save the PDF file
                                //Close the instance of document objects
                                pdfDocument.Save(output);
                                pdfDocument.Close(true);
                                converted = true;

                            }
                        }
                    }
                    catch (Exception e)
                    {
                        string errorMessage = $"Exception occured while coverting a document file, exception :  {e.Message}";
                        message = $"Exception happened while accessing File, re-attempting count : {attempt} , Error Message : {e.Message} , Stack trace : {e.StackTrace}";
                        Log.Error(message);
                        Console.WriteLine(message);
                        if (attempt == FailureAttemptCount)
                        {
                            throw new Exception(errorMessage);
                        }
                        Thread.Sleep(WaitTimeinMilliSeconds);
                    }
                }
            }
            catch (Exception ex)
            {
                converted = false;
                string error = $"Exception occured while coverting Doc file, exception :  {ex.Message} , stacktrace : {ex.StackTrace}";
                Log.Error(error);
                Console.WriteLine(error);
                throw;
            }
            return (converted, output);
        }

        public void Dispose()
        {
            Dispose(true);
            GC.SuppressFinalize(this);
        }

        protected virtual void Dispose(bool disposing)
        {
            if (disposing)
            {
                if (this.SourceStream != null)
                {
                    this.SourceStream.Close();
                    this.SourceStream.Dispose();
                }

                if (output != null) output.Dispose();
                // free managed resources
            }

        }

        /// <summary>
        /// Iterate through each slide in the Presentation.
        /// </summary>
        /// <param name="pptxDoc">The Presentation document.</param>
        public static void ConvertEMFToPNG(IPresentation pptxDoc)
        {
            //Iterate in master slides.
            foreach (IMasterSlide masterSlide in pptxDoc.Masters)
            {
                foreach (ILayoutSlide layoutSlide in masterSlide.LayoutSlides)
                {
                    //Iterate in layout slide.
                    IterateShapes(layoutSlide.Shapes);
                }
                IterateShapes(masterSlide.Shapes);
            }
            //Iterate in slides.
            foreach (ISlide slide in pptxDoc.Slides)
            {
                //Iterate in layout slide.
                IterateShapes(slide.LayoutSlide.Shapes);
                IterateShapes(slide.Shapes);
            }
        }

        /// <summary>
        /// Iterate through each shapes in the slide.
        /// </summary>
        /// <param name="shapes">The shapes.</param>
        public static void IterateShapes(IShapes shapes)
        {
            //Iterate through each shape in the slide.
            for (int i = 0; i < shapes.Count; i++)
            {
                IShape shape = (IShape)shapes[i];
                //Identify the slide item type of the shape.
                switch (shape.SlideItemType)
                {
                    case SlideItemType.Picture:
                        IPicture picture = shape as IPicture;

                        Image image = Image.FromStream(new MemoryStream(picture.ImageData));
                        if (image.RawFormat.Equals(ImageFormat.Emf))
                        {
                            double height = picture.Height;
                            double width = picture.Width;
                            using (FileStream imgFile = new FileStream("Output.png", FileMode.OpenOrCreate, FileAccess.ReadWrite))
                            {
                                image.Save(imgFile, ImageFormat.Png);
                                image.Dispose();
                            }

                            using (FileStream imageStream = new FileStream(@"Output.png", FileMode.Open, FileAccess.ReadWrite))
                            {
                                //Creates instance for memory stream
                                using (MemoryStream memoryStream = new MemoryStream())
                                {
                                    //Copies stream to memoryStream.
                                    imageStream.CopyTo(memoryStream);
                                    //Replaces the existing image with new image.
                                    picture.ImageData = memoryStream.ToArray();
                                    picture.Height = height;
                                    picture.Width = width;
                                }
                            }
                        }
                        break;
                    case SlideItemType.GroupShape:
                        IGroupShape groupShape = (IGroupShape)shape;
                        //Iterate the shape collection in a group shape.
                        IterateShapes(groupShape.Shapes);
                        break;
                    case SlideItemType.AutoShape:
                    case SlideItemType.Placeholder:
                        IShape autoShape = shape as IShape;
                        //Check the fill type of the shape.
                        if (autoShape.Fill.FillType == FillType.Picture)
                        {
                            //Get the instance for picture Fill.
                            IPictureFill pictureFill = autoShape.Fill.PictureFill;
                            Image fillImage = Image.FromStream(new MemoryStream(pictureFill.ImageBytes));
                            if (fillImage.RawFormat.Equals(ImageFormat.Emf))
                            {
                                using (FileStream imgFile = new FileStream("Output.png", FileMode.OpenOrCreate, FileAccess.ReadWrite))
                                {
                                    fillImage.Save(imgFile, ImageFormat.Png);
                                    fillImage.Dispose();
                                }

                                using (FileStream imageStream = new FileStream(@"Output.png", FileMode.Open, FileAccess.ReadWrite))
                                {
                                    //Creates instance for memory stream
                                    using (MemoryStream memoryStream = new MemoryStream())
                                    {
                                        //Copies stream to memoryStream.
                                        imageStream.CopyTo(memoryStream);
                                        //Replaces the existing image with new image.
                                        pictureFill.ImageBytes = memoryStream.ToArray();
                                    }
                                }
                            }
                        }
                        break;
                    case SlideItemType.OleObject:
                        IOleObject oleObject = shape as IOleObject;

                        Image oleImage = Image.FromStream(new MemoryStream(oleObject.ImageData));
                        if (oleImage.RawFormat.Equals(ImageFormat.Emf))
                        {
                            double height = oleObject.Height;
                            double width = oleObject.Width;
                            double left = oleObject.Left;
                            double top = oleObject.Top;

                            FileStream imgFile = new FileStream("Output.png", FileMode.OpenOrCreate, FileAccess.ReadWrite);
                            oleImage.Save(imgFile, ImageFormat.Png);


                            //Gets the data of Ole object.
                            byte[] array = oleObject.ObjectData;
                            //Convert Ole object data into memory system
                            MemoryStream objectStream = new MemoryStream(array);

                            //Gets the ProgID of OLE Object
                            string progID = oleObject.ProgID;

                            //Removed the existing OLE object.
                            shapes.Remove(oleObject);

                            //Add an new OLE object to the slide with PNG format image.
                            IOleObject replacedOleObject = shapes.AddOleObject(imgFile, progID, objectStream);
                            //Set size and position of the OLE object
                            replacedOleObject.Left = left;
                            replacedOleObject.Top = top;
                            replacedOleObject.Width = width;
                            replacedOleObject.Height = height;

                            //Dispose all the instance.
                            imgFile.Dispose();
                            objectStream.Dispose();
                            oleImage.Dispose();
                        }

                        break;
                }
            }
        }
    }
}