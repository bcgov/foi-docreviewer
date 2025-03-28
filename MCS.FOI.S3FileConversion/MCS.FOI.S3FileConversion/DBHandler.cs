﻿using Npgsql;
﻿using System;
using System.Collections;
using System.Collections.Generic;
using System.Security.Cryptography;
using System.Text.Json;
using Ical.Net.DataTypes;
using MCS.FOI.S3FileConversion.Utilities;
using NpgsqlTypes;
using StackExchange.Redis;


namespace MCS.FOI.S3FileConversion
{
    internal class DBHandler : IDisposable
    {
        NpgsqlConnection conn = null;
        public  async System.Threading.Tasks.Task<S3AccessKeys> getAccessKeyFromDB(string bucket)
        {
            S3AccessKeys s3AccessKeys = new S3AccessKeys();
            try
            {                
                conn = getSqlConnection();
                await conn.OpenAsync();

                // Retrieve access key
                await using (var cmd = new NpgsqlCommand("SELECT attributes FROM \"DocumentPathMapper\" where bucket='" + bucket + "';", conn))
                await using (var reader = await cmd.ExecuteReaderAsync())
                {
                    while (await reader.ReadAsync())
                    {
                        string res = reader.GetString(0);                       
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
            finally 
            {
                if (conn != null)
                    conn.Close();
            }
            return s3AccessKeys;
        }

        public  async System.Threading.Tasks.Task recordJobStart(StreamEntry message)
        {
            try
            {
                conn = getSqlConnection();
                await conn.OpenAsync();

                // Insert entry to mark job start
                await using var cmd = new NpgsqlCommand(@"INSERT INTO ""FileConversionJob""
                    (fileconversionjobid, version, ministryrequestid, batch, trigger, inputdocumentmasterid, filename, status)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8) returning fileconversionjobid", conn)

                {
                    Parameters =
                    {
                        new() { Value = (int) message["jobid"],  NpgsqlDbType = NpgsqlDbType.Integer},
                        new() { Value = 2, NpgsqlDbType = NpgsqlDbType.Integer }, // Job start is always the second entry in db
                        new() { Value = (int) message["ministryrequestid"], NpgsqlDbType = NpgsqlDbType.Integer },
                        new() { Value = message["batch"].ToString(), NpgsqlDbType = NpgsqlDbType.Varchar },
                        new() { Value = message["trigger"].ToString(), NpgsqlDbType = NpgsqlDbType.Varchar },
                        new() { Value = (int) message["documentmasterid"], NpgsqlDbType = NpgsqlDbType.Integer },
                        new() { Value = message["filename"].ToString(), NpgsqlDbType = NpgsqlDbType.Varchar},
                        new() { Value = "started", NpgsqlDbType = NpgsqlDbType.Varchar },
                    }
                };
                await cmd.ExecuteNonQueryAsync();
                
            }
            catch (Exception ex)
            {
                Console.WriteLine($" Error happpened while accessing DB. Exception message : {ex.Message} , StackTrace :{ex.StackTrace}");
                throw;
            }
            finally
            {
                if (conn != null)
                    conn.Close();
            }
            return;
        }

        public  async System.Threading.Tasks.Task<Dictionary<string, Dictionary<string, string>>> recordJobEnd(StreamEntry message, bool error, string jobMessage, List<Dictionary<string, string>> attachments)
        {
            Dictionary<string, Dictionary<string, string>> jobIDs = new();
            try
            {
                conn = getSqlConnection();

                await conn.OpenAsync();

                await using var batch = new NpgsqlBatch(conn);

                if (!error)
                {
                    // Insert any child conversion / dedupe tasks first
                    if (attachments != null && attachments.Count > 0)
                    {
                        
                        foreach (var attachment in attachments)
                        {
                            string extension = Path.GetExtension(attachment["filename"]);
                            if (Array.IndexOf(ConversionSettings.ConversionFormats, extension.ToLower()) == -1)
                            {
                                var query = new NpgsqlBatchCommand(@"
                                    with masterid as (INSERT INTO ""DocumentMaster""
                                    (filepath, ministryrequestid, parentid, isredactionready, createdby)
                                    VALUES ($1, $2, $3, $4, $5) returning documentmasterid),
                                    attributeid as (INSERT INTO ""DocumentAttributes""
                                    (documentmasterid, attributes, createdby, version, isactive)
                                    VALUES ((select documentmasterid from masterid), $6, $7, 1, true))
                                    INSERT INTO ""DeduplicationJob""
                                    (version, ministryrequestid, batch, type, trigger, documentmasterid, filename, status)
                                    VALUES ($8, $9, $10, $11, $12,  (select documentmasterid from masterid), $13, $14) returning deduplicationjobid, (select documentmasterid from masterid)")
                                {
                                    Parameters =
                                    {
                                        new() { Value = attachment["filepath"] , NpgsqlDbType = NpgsqlDbType.Varchar},
                                        new() { Value = (int) message["ministryrequestid"] , NpgsqlDbType = NpgsqlDbType.Integer},
                                        new() { Value = (int) message["documentmasterid"] , NpgsqlDbType = NpgsqlDbType.Integer},
                                        new() { Value = false, NpgsqlDbType = NpgsqlDbType.Boolean},
                                        new() { Value = "conversionservice" , NpgsqlDbType = NpgsqlDbType.Varchar},
                                        new() { Value = attachment["attributes"] , NpgsqlDbType = NpgsqlDbType.Json},
                                        new() { Value = "{\"user\": \"conversionservice\"}" , NpgsqlDbType = NpgsqlDbType.Json},
                                        new() { Value = 1 , NpgsqlDbType = NpgsqlDbType.Integer},
                                        new() { Value = (int) message["ministryrequestid"] , NpgsqlDbType = NpgsqlDbType.Integer},
                                        new() { Value = message["batch"].ToString() , NpgsqlDbType = NpgsqlDbType.Varchar},
                                        new() { Value = "rank1" , NpgsqlDbType = NpgsqlDbType.Varchar},
                                        new() { Value = "fileconversion" , NpgsqlDbType = NpgsqlDbType.Varchar},
                                        new() { Value = attachment["filename"].ToString(), NpgsqlDbType = NpgsqlDbType.Varchar},
                                        new() { Value = "pushedtostream", NpgsqlDbType = NpgsqlDbType.Varchar }
                                    }
                                };
                                batch.BatchCommands.Add(query);

                            }
                            else
                            {
                                var query = new NpgsqlBatchCommand(@"
                                    with masterid as (INSERT INTO ""DocumentMaster""
                                    (filepath, ministryrequestid, parentid, isredactionready, createdby)
                                    VALUES ($1, $2, $3, $4, $5) returning documentmasterid),
                                    attributeid as (INSERT INTO ""DocumentAttributes""
                                    (documentmasterid, attributes, createdby, version, isactive)
                                    VALUES ((select documentmasterid from masterid), $6, $7, 1, true))
                                    INSERT INTO ""FileConversionJob""
                                    (version, ministryrequestid, batch, trigger, inputdocumentmasterid, filename, status)
                                    VALUES ($8, $9, $10, $11, (select documentmasterid from masterid), $12, $13) returning fileconversionjobid, (select documentmasterid from masterid)")
                                {
                                    Parameters =
                                    {
                                        new() { Value = attachment["filepath"].ToString() , NpgsqlDbType = NpgsqlDbType.Varchar},
                                        new() { Value = (int) message["ministryrequestid"] , NpgsqlDbType = NpgsqlDbType.Integer},
                                        new() { Value = (int) message["documentmasterid"] , NpgsqlDbType = NpgsqlDbType.Integer},
                                        new() { Value = false, NpgsqlDbType = NpgsqlDbType.Boolean},
                                        new() { Value = "conversionservice" , NpgsqlDbType = NpgsqlDbType.Varchar},
                                        new() { Value = attachment["attributes"] , NpgsqlDbType = NpgsqlDbType.Json},
                                        new() { Value = "{\"user\": \"conversionservice\"}" , NpgsqlDbType = NpgsqlDbType.Json},
                                        new() { Value = 1 , NpgsqlDbType = NpgsqlDbType.Integer},
                                        new() { Value = (int) message["ministryrequestid"] , NpgsqlDbType = NpgsqlDbType.Integer},
                                        new() { Value = message["batch"].ToString() , NpgsqlDbType = NpgsqlDbType.Varchar},
                                        new() { Value = "attachment" , NpgsqlDbType = NpgsqlDbType.Varchar},
                                        new() { Value = attachment["filename"], NpgsqlDbType = NpgsqlDbType.Varchar},
                                        new() { Value = "pushedtostream" , NpgsqlDbType = NpgsqlDbType.Varchar},
                                    }
                                };

                                batch.BatchCommands.Add(query);                                
                            }
                        }

                    }
                    // Insert dedupe task
                    var cmd1 = new NpgsqlBatchCommand(@"INSERT INTO ""DeduplicationJob""
                                (version, ministryrequestid, batch, type, trigger, documentmasterid, filename, status)
                                VALUES ($1, $2, $3, $4, $5, $6, $7, $8) returning deduplicationjobid")

                    {
                        Parameters =
                        {
                            new() { Value = 1 , NpgsqlDbType = NpgsqlDbType.Integer},
                            new() { Value = (int) message["ministryrequestid"] , NpgsqlDbType = NpgsqlDbType.Integer},
                            new() { Value = message["batch"].ToString() , NpgsqlDbType = NpgsqlDbType.Varchar},
                            new() { Value = "rank1" , NpgsqlDbType = NpgsqlDbType.Varchar},
                            new() { Value = message["trigger"].ToString() , NpgsqlDbType = NpgsqlDbType.Varchar},
                            new() { Value = (int) message["documentmasterid"] , NpgsqlDbType = NpgsqlDbType.Integer},
                            new() { Value = message["filename"].ToString(), NpgsqlDbType = NpgsqlDbType.Varchar},
                            new() { Value = "pushedtostream", NpgsqlDbType = NpgsqlDbType.Varchar }
                        }
                    };

                    batch.BatchCommands.Add(cmd1);



                    // Update current task
                    var cmd2 = new NpgsqlBatchCommand(@"
                        with masterid as (INSERT INTO ""DocumentMaster""
                        (filepath, ministryrequestid, processingparentid, isredactionready, createdby)
                        VALUES ($1, $2, $3, $4, $5) returning documentmasterid)
                        INSERT INTO ""FileConversionJob""
                        (fileconversionjobid, version, ministryrequestid, batch, trigger, inputdocumentmasterid, outputdocumentmasterid, filename, status, message)
                        VALUES ($6, $7, $8, $9, $10, $11, (select documentmasterid from masterid), $12, $13, $14) returning (select documentmasterid from masterid)")

                        {
                            Parameters =
                        {
                            new() { Value = Path.ChangeExtension(message["s3filepath"], ".pdf"), NpgsqlDbType = NpgsqlDbType.Varchar},
                            new() { Value = (int) message["ministryrequestid"] , NpgsqlDbType = NpgsqlDbType.Integer},
                            new() { Value = (int) message["documentmasterid"] , NpgsqlDbType = NpgsqlDbType.Integer},
                            new() { Value = false, NpgsqlDbType = NpgsqlDbType.Boolean},
                            new() { Value = "conversionservice" , NpgsqlDbType = NpgsqlDbType.Varchar},
                            new() { Value = (int) message["jobid"] , NpgsqlDbType = NpgsqlDbType.Integer},
                            new() { Value = 3 , NpgsqlDbType = NpgsqlDbType.Integer}, // Job end is always the third entry in db
                            new() { Value = (int) message["ministryrequestid"] , NpgsqlDbType = NpgsqlDbType.Integer},
                            new() { Value = message["batch"].ToString() , NpgsqlDbType = NpgsqlDbType.Varchar},
                            new() { Value = message["trigger"].ToString() , NpgsqlDbType = NpgsqlDbType.Varchar},
                            new() { Value = (int) message["documentmasterid"] , NpgsqlDbType = NpgsqlDbType.Integer},
                            new() { Value = message["filename"].ToString(), NpgsqlDbType = NpgsqlDbType.Varchar},
                            new() { Value = "completed", NpgsqlDbType = NpgsqlDbType.Varchar},
                            new() { Value = jobMessage, NpgsqlDbType = NpgsqlDbType.Text }
                        }
                    };
                    batch.BatchCommands.Add(cmd2);
                } else
                {
                    // Update current task
                    var cmd2 = new NpgsqlBatchCommand(@"
                        INSERT INTO ""FileConversionJob""
                        (fileconversionjobid, version, ministryrequestid, batch, trigger, inputdocumentmasterid, filename, status, message)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9) ")

                        {
                            Parameters =
                        {
                            new() { Value = (int) message["jobid"] , NpgsqlDbType = NpgsqlDbType.Integer},
                            new() { Value = 3 , NpgsqlDbType = NpgsqlDbType.Integer}, // Job end is always the third entry in db
                            new() { Value = (int) message["ministryrequestid"] , NpgsqlDbType = NpgsqlDbType.Integer},
                            new() { Value = message["batch"].ToString() , NpgsqlDbType = NpgsqlDbType.Varchar},
                            new() { Value = message["trigger"].ToString() , NpgsqlDbType = NpgsqlDbType.Varchar},
                            new() { Value = (int) message["documentmasterid"] , NpgsqlDbType = NpgsqlDbType.Integer},
                            new() { Value = message["filename"].ToString(), NpgsqlDbType = NpgsqlDbType.Varchar},
                            new() { Value = "error", NpgsqlDbType = NpgsqlDbType.Varchar},
                            new() { Value = jobMessage, NpgsqlDbType = NpgsqlDbType.Text }
                        }
                    };
                    batch.BatchCommands.Add(cmd2);
                }
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
                            string attachmentMasterID = reader.GetInt32(1).ToString();
                            
                            jobIDs.Add(attachment["filepath"], new Dictionary<string, string> { { "jobID", jobID }, { "masterID", attachmentMasterID } });
                            await reader.NextResultAsync();
                        }

                        await reader.ReadAsync();
                        string dedupeJobID = reader.GetInt32(0).ToString();                       
                        await reader.NextResultAsync();
                        await reader.ReadAsync();
                        string masterID = reader.GetInt32(0).ToString();                       
                        jobIDs.Add(Path.ChangeExtension(message["s3filepath"], ".pdf"), new Dictionary<string, string> { { "jobID", dedupeJobID }, { "masterID", masterID } });
                    }
                }
                
            }
            catch (Exception ex)
            {
                Console.WriteLine($" Error happpened while accessing DB. Exception message : {ex.Message} , StackTrace :{ex.StackTrace}");
                throw;
            }
            finally
            {
                if (conn != null)
                    conn.Close();
            }

            return jobIDs;
        }

        private NpgsqlConnection getSqlConnection()
        {
            var host = Environment.GetEnvironmentVariable("DATABASE_HOST");
            var port = Environment.GetEnvironmentVariable("DATABASE_PORT");
            var dbname = Environment.GetEnvironmentVariable("DATABASE_NAME");
            var username = Environment.GetEnvironmentVariable("DATABASE_USERNAME");
            var password = Environment.GetEnvironmentVariable("DATABASE_PASSWORD");
            string _connectionString = "Host=" + host + ";Port=" + port + ";Username=" + username + "; Password=" + password + ";Database=" + dbname + ";";
            return new NpgsqlConnection(_connectionString);            
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
                if (conn != null)
                {
                    if (conn.State != System.Data.ConnectionState.Closed)
                        conn.Close();
                    conn.Dispose();
                }
                   
                // free managed resources
            }

        }

    }
}