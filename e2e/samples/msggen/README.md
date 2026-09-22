# msggen

Generates `../msg-with-attachments.msg`: a synthetic Outlook email with two
inline images and N generic `.msg` attachments, so the e2e msg pipeline test
exercises attachment extraction without shipping real correspondence.

```sh
dotnet run --project e2e/samples/msggen -- e2e/samples/msg-with-attachments.msg 14
```

If you change the attachment count, update `ATTACHMENT_COUNT` in
`e2e/tests/test_msg_pipeline.py`.
