using System;
using System.Collections;
using System.Collections.Generic;
using System.Text.Json;
using Ical.Net.DataTypes;
using Npgsql;
using NpgsqlTypes;
using Serilog;
using StackExchange.Redis;


namespace MCS.FOI.S3FileConversion
{
    internal class DBHandler
    {
        public static async System.Threading.Tasks.Task<S3AccessKeys> getAccessKeyFromDB(string bucket)
        {
            S3AccessKeys s3AccessKeys = new S3AccessKeys();
            try
            {
                var connString = getConnectionString();

                await using var conn = new NpgsqlConnection(connString);
                await conn.OpenAsync();

                // Retrieve access key
                await using (var cmd = new NpgsqlCommand("SELECT attributes FROM \"DocumentPathMapper\" where bucket='" + bucket + "';", conn))
                await using (var reader = await cmd.ExecuteReaderAsync())
                {
                    while (await reader.ReadAsync())
                    {
                        string res = reader.GetString(0);
                        Console.WriteLine(res);
                        s3AccessKeys = JsonSerializer.Deserialize<S3AccessKeys>(res);
                    }
                }
                conn.Close();
            }
            catch (Exception ex)
            {
                Console.WriteLine($" Error happpened while accessing DB. Exception message : {ex.Message} , StackTrace :{ex.StackTrace}");
                throw;
            }
            return s3AccessKeys;
        }

        public static async System.Threading.Tasks.Task recordJobStart(StreamEntry message)
        {
            try
            {
                var connString = getConnectionString();

                await using var conn = new NpgsqlConnection(connString);
                await conn.OpenAsync();

                // Insert entry to mark job start
                await using var cmd = new NpgsqlCommand(@"INSERT INTO ""FileConversionJob"" 
                    (fileconversionjobid, version, ministryrequestid, batch, trigger, inputfilepath, filename, status, parentfilepath, parentfilename) 
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10) returning fileconversionjobid", conn)
                
                {
                    Parameters =
                    {
                        new() { Value = (int) message["jobid"],  NpgsqlDbType = NpgsqlDbType.Integer},
                        new() { Value = 2, NpgsqlDbType = NpgsqlDbType.Integer }, // Job start is always the second entry in db
                        new() { Value = (int) message["ministryrequestid"], NpgsqlDbType = NpgsqlDbType.Integer },
                        new() { Value = message["batch"].ToString(), NpgsqlDbType = NpgsqlDbType.Varchar },
                        new() { Value = message["trigger"].ToString(), NpgsqlDbType = NpgsqlDbType.Varchar },
                        new() { Value = message["s3filepath"].ToString(), NpgsqlDbType = NpgsqlDbType.Varchar },
                        new() { Value = message["filename"].ToString(), NpgsqlDbType = NpgsqlDbType.Varchar},
                        new() { Value = "started", NpgsqlDbType = NpgsqlDbType.Varchar },
                        new() { Value = message["parentfilepath"].ToString(), NpgsqlDbType = NpgsqlDbType.Varchar },
                        new() { Value = message["parentfilename"].ToString(), NpgsqlDbType = NpgsqlDbType.Varchar }
                    }
                };
                await cmd.ExecuteNonQueryAsync();
                conn.Close();
            }
            catch (Exception ex)
            {
                Console.WriteLine($" Error happpened while accessing DB. Exception message : {ex.Message} , StackTrace :{ex.StackTrace}");
                throw;
            }
            return;
        }

        public static async System.Threading.Tasks.Task<Dictionary<string, string>> recordJobEnd(StreamEntry message, bool error, string jobMessage, List<Dictionary<string, string>> attachments)
        {
            Dictionary<string, string>  jobIDs = new();
            try
            {
                var connString = getConnectionString();

                await using var conn = new NpgsqlConnection(connString);
                await conn.OpenAsync();

                await using var batch = new NpgsqlBatch(conn);

                if (!error)
                {
                    // Insert any child conversion tasks first
                    if (attachments != null && attachments.Count > 0)
                    {
                        foreach (var attachment in attachments)
                        {
                            string extension = Path.GetExtension(attachment["filename"]);
                            string[] conversionFormats = { ".doc", ".docx", ".xls", ".xlsx", ".ics", ".msg" };
                            if (Array.IndexOf(conversionFormats, extension) == -1)
                            {
                                var query = new NpgsqlBatchCommand(@"INSERT INTO ""DeduplicationJob"" 
                                    (version, ministryrequestid, batch, type, trigger, filepath, filename, status) 
                                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8) returning deduplicationjobid")
                                {
                                    Parameters =
                                    {
                                        new() { Value = 1 , NpgsqlDbType = NpgsqlDbType.Integer},
                                        new() { Value = (int) message["ministryrequestid"] , NpgsqlDbType = NpgsqlDbType.Integer},
                                        new() { Value = message["batch"].ToString() , NpgsqlDbType = NpgsqlDbType.Varchar},
                                        new() { Value = "rank1" , NpgsqlDbType = NpgsqlDbType.Varchar},
                                        new() { Value = "fileconversion" , NpgsqlDbType = NpgsqlDbType.Varchar},
                                        new() { Value = attachment["filepath"].ToString() , NpgsqlDbType = NpgsqlDbType.Varchar},
                                        new() { Value = attachment["filename"].ToString(), NpgsqlDbType = NpgsqlDbType.Varchar},
                                        new() { Value = "pushedtostream", NpgsqlDbType = NpgsqlDbType.Varchar }
                                    }
                                };
                                batch.BatchCommands.Add(query);

                            } 
                            else
                            {
                                var query = new NpgsqlBatchCommand(@"INSERT INTO ""FileConversionJob"" 
                                (version, ministryrequestid, batch, trigger, inputfilepath, filename, status, parentfilepath, parentfilename) 
                                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) returning fileconversionjobid")
                                {
                                    Parameters =
                                    {
                                        new() { Value = 1 , NpgsqlDbType = NpgsqlDbType.Integer},
                                        new() { Value = (int) message["ministryrequestid"] , NpgsqlDbType = NpgsqlDbType.Integer},
                                        new() { Value = message["batch"].ToString() , NpgsqlDbType = NpgsqlDbType.Varchar},
                                        new() { Value = "attachment" , NpgsqlDbType = NpgsqlDbType.Varchar},
                                        new() { Value = attachment["filepath"] , NpgsqlDbType = NpgsqlDbType.Varchar},
                                        new() { Value = attachment["filename"], NpgsqlDbType = NpgsqlDbType.Varchar},
                                        new() { Value = "pushedtostream" , NpgsqlDbType = NpgsqlDbType.Varchar},
                                        new() { Value = message["s3filepath"].ToString() , NpgsqlDbType = NpgsqlDbType.Varchar},
                                        new() { Value = message["filename"].ToString(), NpgsqlDbType = NpgsqlDbType.Varchar }
                                    }
                                };

                                batch.BatchCommands.Add(query);
                            }
                        }

                    }
                    // Insert dedupe task
                    var cmd1 = new NpgsqlBatchCommand(@"INSERT INTO ""DeduplicationJob"" 
                                (version, ministryrequestid, batch, type, trigger, filepath, filename, status) 
                                VALUES ($1, $2, $3, $4, $5, $6, $7, $8) returning deduplicationjobid")

                    {
                        Parameters =
                        {                            
                            new() { Value = 1 , NpgsqlDbType = NpgsqlDbType.Integer},
                            new() { Value = (int) message["ministryrequestid"] , NpgsqlDbType = NpgsqlDbType.Integer},
                            new() { Value = message["batch"].ToString() , NpgsqlDbType = NpgsqlDbType.Varchar},
                            new() { Value = "rank1" , NpgsqlDbType = NpgsqlDbType.Varchar},
                            new() { Value = "fileconversion" , NpgsqlDbType = NpgsqlDbType.Varchar},
                            new() { Value = Path.ChangeExtension(message["s3filepath"].ToString(), ".pdf") , NpgsqlDbType = NpgsqlDbType.Varchar},
                            new() { Value = message["filename"].ToString(), NpgsqlDbType = NpgsqlDbType.Varchar},
                            new() { Value = "pushedtostream", NpgsqlDbType = NpgsqlDbType.Varchar }
                        }
                    };

                    batch.BatchCommands.Add(cmd1);
                }


                // Update current task
                var cmd2 = new NpgsqlBatchCommand(@"INSERT INTO ""FileConversionJob"" 
                    (fileconversionjobid, version, ministryrequestid, batch, trigger, inputfilepath, outputfilepath, filename, status, parentfilepath, parentfilename, message) 
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)")

                {
                    Parameters =
                    {
                        new() { Value = (int) message["jobid"] , NpgsqlDbType = NpgsqlDbType.Integer},
                        new() { Value = 3 , NpgsqlDbType = NpgsqlDbType.Integer}, // Job end is always the third entry in db
                        new() { Value = (int) message["ministryrequestid"] , NpgsqlDbType = NpgsqlDbType.Integer},
                        new() { Value = message["batch"].ToString() , NpgsqlDbType = NpgsqlDbType.Varchar},
                        new() { Value = message["trigger"].ToString() , NpgsqlDbType = NpgsqlDbType.Varchar},
                        new() { Value = message["s3filepath"].ToString() , NpgsqlDbType = NpgsqlDbType.Varchar},
                        new() { Value = Path.ChangeExtension(message["s3filepath"], ".pdf"), NpgsqlDbType = NpgsqlDbType.Varchar},
                        new() { Value = message["filename"].ToString(), NpgsqlDbType = NpgsqlDbType.Varchar},
                        new() { Value = error ? "error" : "completed", NpgsqlDbType = NpgsqlDbType.Varchar},
                        new() { Value = message["parentfilepath"].ToString() , NpgsqlDbType = NpgsqlDbType.Varchar},
                        new() { Value = message["parentfilename"].ToString() , NpgsqlDbType = NpgsqlDbType.Varchar},
                        new() { Value = jobMessage, NpgsqlDbType = NpgsqlDbType.Text }
                    }
                };
                batch.BatchCommands.Add(cmd2);
                if (error)
                {
                    await batch.ExecuteNonQueryAsync();

                } 
                else
                {
                    await using (var reader = await batch.ExecuteReaderAsync())
                    {
                        foreach (var attachment in attachments)
                        {
                            await reader.ReadAsync();
                            string jobID = reader.GetInt32(0).ToString();
                            Console.WriteLine(jobID);
                            jobIDs.Add(attachment["filepath"], jobID);
                            await reader.NextResultAsync();
                        }

                        await reader.ReadAsync();
                        string dedupeJobID = reader.GetInt32(0).ToString();
                        Console.WriteLine(dedupeJobID);
                        jobIDs.Add(Path.ChangeExtension(message["s3filepath"], ".pdf"), dedupeJobID);
                    }
                }
                conn.Close();
            }
            catch (Exception ex)
            {
                Console.WriteLine($" Error happpened while accessing DB. Exception message : {ex.Message} , StackTrace :{ex.StackTrace}");
                throw;
            }
            return jobIDs;
        }

        private static String getConnectionString()
        {
            var host = Environment.GetEnvironmentVariable("DATABASE_HOST");
            var port = Environment.GetEnvironmentVariable("DATABASE_PORT");
            var dbname = Environment.GetEnvironmentVariable("DATABASE_NAME");
            var username = Environment.GetEnvironmentVariable("DATABASE_USERNAME");
            var password = Environment.GetEnvironmentVariable("DATABASE_PASSWORD");
            return "Host=" + host + ";Port=" + port + ";Username=" + username + "; Password=" + password + ";Database=" + dbname + ";";
        }

    }
}