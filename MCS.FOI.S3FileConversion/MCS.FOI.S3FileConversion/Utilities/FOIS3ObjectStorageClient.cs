using Amazon.Runtime;
using Amazon.S3;

namespace MCS.FOI.S3FileConversion.Utilities
{
    public class FOIS3ObjectStorageClient : IDisposable
    {
        public string _S3AccessKeyID { get; set; }
        public string _S3AccessSecretKey { get; set; }

        public FOIS3ObjectStorageClient()
        {

        }
        public FOIS3ObjectStorageClient(string S3AccessKeyID, string S3AccessSecretKey) {

            _S3AccessKeyID = S3AccessKeyID;
            _S3AccessSecretKey = S3AccessSecretKey;
        }

        IAmazonS3 s3;
        private AWSCredentials _AWSCredentials;
        public IAmazonS3 getS3Client()
        {
                        
            _AWSCredentials = new BasicAWSCredentials(_S3AccessKeyID, _S3AccessSecretKey);
            AmazonS3Config config = new()
            {
                ServiceURL = gets3host()
            };

            s3 = new AmazonS3Client(_AWSCredentials, config);

            return s3;
        }


        public string gets3host()
        {
            var configured = Environment.GetEnvironmentVariable("S3_HOST");
            if (string.IsNullOrWhiteSpace(configured))
            {
                throw new InvalidOperationException("S3_HOST is required");
            }

            var endpoint = configured.Trim();
            if (!endpoint.StartsWith("http://", StringComparison.OrdinalIgnoreCase) &&
                !endpoint.StartsWith("https://", StringComparison.OrdinalIgnoreCase))
            {
                endpoint = $"https://{endpoint}";
            }

            if (!Uri.TryCreate(endpoint, UriKind.Absolute, out var uri) ||
                (uri.Scheme != Uri.UriSchemeHttp && uri.Scheme != Uri.UriSchemeHttps))
            {
                throw new InvalidOperationException("S3_HOST must be an HTTP or HTTPS endpoint");
            }

            return endpoint.TrimEnd('/');
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
                if (s3 != null)
                {
                    s3.Dispose();                   
                }
               
            }
            // free native resources if there are any.
        }
    }
}
